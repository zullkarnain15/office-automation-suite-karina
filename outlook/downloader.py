"""
Outlook Object Model integration for Outlook - Revisi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import format_datetime
from email.utils import make_msgid
from email.message import EmailMessage
from pathlib import Path
import re
import smtplib
import time
from typing import Any
from typing import Callable
from uuid import uuid4

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class OutlookAttachment:
    """Saved Outlook attachment metadata."""

    file_name: str
    path: Path


@dataclass(slots=True)
class OutlookMessage:
    """Outlook message snapshot used by the engine."""

    entry_id: str
    store_id: str
    subject: str
    sender_name: str
    sender_email: str
    cc: str
    received_time: datetime | None
    attachments: list[OutlookAttachment]
    raw_item: Any = None
    attachment_count: int = 0


@dataclass(slots=True)
class SmtpSentCopyResult:
    """Lifecycle state for one SMTP BCC archive copy."""

    copy_id: str
    message_id: str = ""
    subject: str = ""
    status: str = "BCC_QUEUED"
    detail: str = ""
    created_at: datetime | None = None
    moved_at: datetime | None = None


class OutlookComClient:
    """Thin wrapper around Microsoft Outlook COM automation."""

    OL_FOLDER_INBOX = 6
    OL_FOLDER_DELETED_ITEMS = 3
    OL_FOLDER_SENT_MAIL = 5
    TRANSPORT_HEADERS_PROPERTIES = (
        "http://schemas.microsoft.com/mapi/proptag/0x007D001F",
        "http://schemas.microsoft.com/mapi/proptag/0x007D001E",
    )
    SMTP_COPY_HEADER = "X-OAS-K-Copy-ID"

    def __init__(
        self,
        mailbox_smtp: str,
        source_folder: str = "Inbox",
        reply_from_smtp: str | None = None,
        send_transport: str = "OUTLOOK",
        smtp_server: str = "",
        smtp_port: int = 25,
        smtp_timeout: int = 30,
        save_smtp_copy_to_sent: bool = True,
    ) -> None:
        self.mailbox_smtp = mailbox_smtp.strip().lower()
        self.source_folder = source_folder.strip() or "Inbox"
        self.reply_from_smtp = (reply_from_smtp or mailbox_smtp).strip().lower()
        self.send_transport = send_transport.strip().upper() or "OUTLOOK"
        if self.send_transport not in {"OUTLOOK", "SMTP"}:
            raise ValueError(
                "Send_Transport must be OUTLOOK or SMTP, got: "
                f"{send_transport}"
            )
        self.smtp_server = smtp_server.strip()
        self.smtp_port = int(smtp_port)
        self.smtp_timeout = int(smtp_timeout)
        self.save_smtp_copy_to_sent = bool(save_smtp_copy_to_sent)
        self._outlook = None
        self._namespace = None
        self._smtp_copy_results: dict[str, SmtpSentCopyResult] = {}

    def connect(self) -> None:
        """Connect to Outlook through COM."""
        try:
            import win32com.client  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError(
                "pywin32 is required for Outlook COM automation. "
                "Install dependency first: py -m pip install pywin32"
            ) from error

        try:
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._namespace = self._outlook.GetNamespace("MAPI")
        except Exception as error:
            error_code = getattr(error, "hresult", None)
            if error_code is None and getattr(error, "args", None):
                error_code = error.args[0]

            # REGDB_E_CLASSNOTREG. This commonly happens when only New Outlook
            # is available, or when an Outlook Classic installation has lost
            # its COM registration.
            if error_code == -2147221005:
                raise RuntimeError(
                    "Outlook Classic tidak terdaftar untuk COM automation. "
                    "New Outlook tidak mendukung fitur ini. Pastikan Outlook "
                    "Classic terpasang, lalu jalankan Repair Microsoft 365 "
                    "atau daftarkan ulang Outlook Classic, dan buka Outlook "
                    "sekali sebelum mencoba kembali."
                ) from error

            raise RuntimeError(
                "Tidak dapat membuka Outlook Classic melalui COM automation. "
                "Pastikan Outlook Classic sudah terbuka dan profil email "
                "dapat diakses. Detail: " + str(error)
            ) from error
        logger.info("Connected to Outlook COM.")

    def fetch_messages(
        self,
        attachment_folder: str | Path,
        limit: int | None = None,
        message_filter: Callable[[OutlookMessage], bool] | None = None,
        attachment_filter: Callable[[OutlookMessage], bool] | None = None,
    ) -> list[OutlookMessage]:
        """Fetch candidate messages and save only selected attachments."""
        if self._namespace is None:
            self.connect()

        folder = self._get_source_folder()
        items = folder.Items
        try:
            items.Sort("[ReceivedTime]", True)
        except Exception:
            logger.warning("Could not sort Outlook Inbox by ReceivedTime.")

        output_folder = Path(attachment_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        messages: list[OutlookMessage] = []
        count = 0

        for item in items:
            if limit is not None and count >= limit:
                break

            if getattr(item, "Class", None) != 43:
                continue

            sender_email = self._get_sender_email(item)
            if self._is_smtp_archive_message(item, sender_email):
                logger.info(
                    "Skipping OAS-K SMTP BCC archive in Inbox: %s",
                    str(getattr(item, "Subject", "") or ""),
                )
                continue

            message = OutlookMessage(
                entry_id=str(getattr(item, "EntryID", "") or ""),
                store_id=str(getattr(item, "Parent", "").StoreID)
                if getattr(item, "Parent", None) is not None
                else "",
                subject=str(getattr(item, "Subject", "") or ""),
                sender_name=str(getattr(item, "SenderName", "") or ""),
                sender_email=sender_email,
                cc=self._get_cc_emails(item),
                received_time=self._safe_datetime(
                    getattr(item, "ReceivedTime", None)
                ),
                attachments=[],
                raw_item=item,
                attachment_count=int(
                    getattr(getattr(item, "Attachments", None), "Count", 0) or 0
                ),
            )
            if message_filter is not None and not message_filter(message):
                continue

            if attachment_filter is None or attachment_filter(message):
                message.attachments = self._save_attachments(item, output_folder)
            messages.append(message)
            count += 1

        return messages

    def send_reply(
        self,
        message: OutlookMessage,
        subject: str,
        body: str,
        to: str | None = None,
        cc: str | None = None,
        send_mode: str = "SEND",
    ) -> SmtpSentCopyResult | None:
        """Send or draft a reply using configured Outlook account."""
        if message.raw_item is None:
            logger.warning("Reply skipped because raw Outlook item is missing.")
            return

        if self.send_transport == "SMTP":
            headers: dict[str, str] = {}
            internet_message_id = str(
                getattr(message.raw_item, "InternetMessageID", "") or ""
            ).strip()
            if internet_message_id:
                headers["In-Reply-To"] = internet_message_id
                headers["References"] = internet_message_id
            return self._send_smtp(
                to=[to or message.sender_email],
                cc=self._split_addresses(cc),
                subject=subject,
                body=body,
                send_mode=send_mode,
                headers=headers,
                archive_copy=True,
            )

        reply = message.raw_item.Reply()
        reply.Subject = subject
        reply.Body = body

        if to:
            reply.To = to
        if cc:
            reply.CC = cc

        account = self._find_account(self.reply_from_smtp)
        if account is None:
            raise RuntimeError(
                "Reply account not found in Outlook profile: "
                f"{self.reply_from_smtp}"
            )
        reply.SendUsingAccount = account

        if send_mode.strip().upper() == "DRAFT":
            reply.Save()
        else:
            reply.Send()
        return None

    def send_mail(
        self,
        to: list[str],
        cc: list[str],
        subject: str,
        body: str,
        send_mode: str = "SEND",
    ) -> None:
        """Send or draft a new mail."""
        if self.send_transport == "SMTP":
            self._send_smtp(to, cc, subject, body, send_mode)
            return

        if self._outlook is None:
            self.connect()

        mail = self._outlook.CreateItem(0)
        mail.To = "; ".join(to)
        mail.CC = "; ".join(cc)
        mail.Subject = subject
        mail.Body = body

        account = self._find_account(self.reply_from_smtp)
        if account is None:
            raise RuntimeError(
                "Reply account not found in Outlook profile: "
                f"{self.reply_from_smtp}"
            )
        mail.SendUsingAccount = account

        if send_mode.strip().upper() == "DRAFT":
            mail.Save()
        else:
            mail.Send()

    def _send_smtp(
        self,
        to: list[str],
        cc: list[str],
        subject: str,
        body: str,
        send_mode: str,
        headers: dict[str, str] | None = None,
        archive_copy: bool = False,
    ) -> SmtpSentCopyResult | None:
        """Send mail through the trusted internal SMTP relay."""
        if send_mode.strip().upper() == "DRAFT":
            raise RuntimeError(
                "Send_Mode DRAFT is not supported when Send_Transport is SMTP."
            )
        if not self.smtp_server:
            raise RuntimeError("SMTP_Server is required for SMTP transport.")
        if not self.reply_from_smtp or "@" not in self.reply_from_smtp:
            raise RuntimeError("Reply_From_SMTP must be a valid email address.")

        recipients = self._deduplicate_addresses([*to, *cc])
        if not recipients:
            raise RuntimeError("SMTP message has no recipients.")

        copy_result: SmtpSentCopyResult | None = None
        archive_address = ""
        if archive_copy and self.save_smtp_copy_to_sent:
            archive_address = self.mailbox_smtp.strip().lower()
            copy_id = self._new_smtp_copy_id()
            copy_result = SmtpSentCopyResult(
                copy_id=copy_id,
                subject=subject,
                created_at=datetime.now(),
            )
            self._smtp_copy_results[copy_id] = copy_result
            if not archive_address or "@" not in archive_address:
                copy_result.status = "BCC_REJECTED"
                copy_result.detail = "Mailbox_SMTP is not a valid BCC address."
                archive_address = ""

        mail = EmailMessage()
        mail["From"] = self.reply_from_smtp
        mail["To"] = "; ".join(item.strip() for item in to if item.strip())
        if cc:
            mail["Cc"] = "; ".join(item.strip() for item in cc if item.strip())
        mail["Subject"] = subject
        for name, value in (headers or {}).items():
            if value:
                mail[name] = value
        if copy_result is not None:
            domain = self.reply_from_smtp.partition("@")[2] or None
            copy_result.message_id = make_msgid(
                idstring=copy_result.copy_id,
                domain=domain,
            )
            mail["Message-ID"] = copy_result.message_id
            mail["Date"] = format_datetime(datetime.now().astimezone())
            mail[self.SMTP_COPY_HEADER] = copy_result.copy_id
        mail.set_content(body)

        envelope_recipients = list(recipients)
        if archive_address:
            envelope_recipients = self._deduplicate_addresses(
                [*envelope_recipients, archive_address]
            )

        with smtplib.SMTP(
            self.smtp_server,
            self.smtp_port,
            timeout=self.smtp_timeout,
        ) as smtp:
            refused_response = smtp.send_message(
                mail,
                to_addrs=envelope_recipients,
            )

        refused = (
            {str(address).strip().lower(): detail for address, detail in refused_response.items()}
            if isinstance(refused_response, dict)
            else {}
        )
        if copy_result is not None and copy_result.status != "BCC_REJECTED":
            if archive_address in refused:
                copy_result.status = "BCC_REJECTED"
                copy_result.detail = str(refused[archive_address])
                logger.warning(
                    "SMTP reply sent, but BCC archive recipient was rejected: %s",
                    archive_address,
                )
            else:
                copy_result.status = "BCC_ACCEPTED"
                logger.info(
                    "SMTP BCC archive accepted for %s with copy ID %s.",
                    archive_address,
                    copy_result.copy_id,
                )

        logger.info(
            "Email sent through SMTP relay %s:%s from %s.",
            self.smtp_server,
            self.smtp_port,
            self.reply_from_smtp,
        )

        return copy_result

    def register_pending_smtp_copy(
        self,
        copy_id: str,
        subject: str = "",
    ) -> SmtpSentCopyResult:
        """Register a previous-run BCC copy for idempotent recovery."""
        normalized = str(copy_id or "").strip()
        if not normalized:
            raise ValueError("SMTP sent copy ID cannot be empty.")
        result = self._smtp_copy_results.get(normalized)
        if result is None:
            result = SmtpSentCopyResult(
                copy_id=normalized,
                subject=subject,
                status="COPY_PENDING",
            )
            self._smtp_copy_results[normalized] = result
        return result

    def collect_smtp_sent_copies(
        self,
        copy_ids: set[str] | None = None,
        timeout_seconds: float = 5.0,
        poll_interval: float = 1.0,
    ) -> dict[str, SmtpSentCopyResult]:
        """Move matching BCC replies from shared Inbox to its Sent Items."""
        wanted = {
            copy_id
            for copy_id in (copy_ids or set(self._smtp_copy_results))
            if copy_id in self._smtp_copy_results
            and self._smtp_copy_results[copy_id].status
            in {"BCC_ACCEPTED", "COPY_PENDING", "MOVE_FAILED"}
        }
        if not wanted:
            return {
                copy_id: self._smtp_copy_results[copy_id]
                for copy_id in (copy_ids or set(self._smtp_copy_results))
                if copy_id in self._smtp_copy_results
            }

        if self._namespace is None:
            self.connect()
        inbox = self._get_shared_inbox_folder()
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))

        while wanted:
            matches = self._find_smtp_archive_items(inbox, wanted)
            for copy_id, item in matches.items():
                result = self._smtp_copy_results[copy_id]
                try:
                    self._move_smtp_archive_item(item)
                    result.status = "MOVED_TO_SENT"
                    result.detail = "BCC archive moved to shared Sent Items."
                    result.moved_at = datetime.now()
                    wanted.discard(copy_id)
                    logger.info(
                        "SMTP BCC archive moved to Sent Items: %s",
                        copy_id,
                    )
                except Exception as error:
                    result.status = "MOVE_FAILED"
                    result.detail = str(error)
                    wanted.discard(copy_id)
                    logger.exception(
                        "SMTP BCC archive remains in Inbox because move failed: %s",
                        copy_id,
                    )

            if not wanted or time.monotonic() >= deadline:
                break
            time.sleep(min(max(0.05, poll_interval), max(0.0, deadline - time.monotonic())))

        for copy_id in wanted:
            result = self._smtp_copy_results[copy_id]
            result.status = "COPY_PENDING"
            result.detail = "BCC archive has not arrived in Inbox yet."

        selected = copy_ids or set(self._smtp_copy_results)
        return {
            copy_id: self._smtp_copy_results[copy_id]
            for copy_id in selected
            if copy_id in self._smtp_copy_results
        }

    def get_smtp_copy_result(self, copy_id: str) -> SmtpSentCopyResult | None:
        """Return the current BCC archive state for one reply."""
        return self._smtp_copy_results.get(str(copy_id or "").strip())

    def _get_shared_inbox_folder(self) -> Any:
        try:
            return self._get_mailbox_store().GetDefaultFolder(self.OL_FOLDER_INBOX)
        except RuntimeError:
            return self._get_shared_default_folder(self.OL_FOLDER_INBOX)

    def _find_smtp_archive_items(
        self,
        inbox: Any,
        wanted: set[str],
        scan_limit: int = 500,
    ) -> dict[str, Any]:
        items = inbox.Items
        try:
            items.Sort("[ReceivedTime]", True)
        except Exception:
            logger.warning("Could not sort shared Inbox while finding BCC archives.")

        candidates: list[Any] = []
        try:
            count = min(int(getattr(items, "Count", 0) or 0), scan_limit)
            candidates = [items.Item(index) for index in range(1, count + 1)]
        except Exception:
            candidates = []
            for index, item in enumerate(items):
                if index >= scan_limit:
                    break
                candidates.append(item)

        matches: dict[str, Any] = {}
        for item in candidates:
            if getattr(item, "Class", None) != 43:
                continue
            copy_id = self._smtp_copy_id_from_item(item, wanted)
            if copy_id and copy_id not in matches:
                matches[copy_id] = item
        return matches

    def _move_smtp_archive_item(self, item: Any) -> None:
        parent = getattr(item, "Parent", None)
        source_store = getattr(parent, "Store", None)
        if source_store is None:
            raise RuntimeError("BCC archive source store is unavailable.")
        destination = source_store.GetDefaultFolder(self.OL_FOLDER_SENT_MAIL)
        if destination is None:
            raise RuntimeError("Shared Sent Items folder is unavailable.")

        try:
            if bool(getattr(item, "UnRead", False)):
                item.UnRead = False
                item.Save()
        except Exception:
            logger.warning(
                "BCC archive could not be marked read before moving; "
                "continuing with the Sent Items move."
            )
        moved_item = item.Move(destination)
        try:
            if moved_item is not None and bool(
                getattr(moved_item, "UnRead", False)
            ):
                moved_item.UnRead = False
                moved_item.Save()
        except Exception:
            # Move already succeeded. A read-state failure must not keep the
            # Copy ID in the pending queue forever.
            logger.warning(
                "BCC archive moved to Sent Items but its read state could not "
                "be updated."
            )

    def _is_smtp_archive_message(self, item: Any, sender_email: str) -> bool:
        if self._smtp_copy_id_from_item(item):
            return True
        subject = str(getattr(item, "Subject", "") or "").strip().lower()
        return (
            sender_email.strip().lower() == self.reply_from_smtp
            and subject.startswith(("re:", "fw:", "fwd:"))
        )

    def _smtp_copy_id_from_item(
        self,
        item: Any,
        wanted: set[str] | None = None,
    ) -> str:
        headers = self._transport_headers(item)
        match = re.search(
            rf"(?im)^{re.escape(self.SMTP_COPY_HEADER)}:\s*([^\s]+)",
            headers,
        )
        if match:
            return match.group(1).strip()

        internet_message_id = str(
            getattr(item, "InternetMessageID", "") or ""
        )
        searchable = f"{headers}\n{internet_message_id}".lower()
        for copy_id in wanted or set(self._smtp_copy_results):
            if copy_id.lower() in searchable:
                return copy_id
        return ""

    def _transport_headers(self, item: Any) -> str:
        accessor = getattr(item, "PropertyAccessor", None)
        if accessor is None:
            return ""
        for property_name in self.TRANSPORT_HEADERS_PROPERTIES:
            try:
                value = str(accessor.GetProperty(property_name) or "")
                if value:
                    return value
            except Exception:
                continue
        return ""

    @staticmethod
    def _deduplicate_addresses(values: list[str]) -> list[str]:
        addresses: list[str] = []
        seen: set[str] = set()
        for value in values:
            address = str(value or "").strip()
            normalized = address.lower()
            if not address or normalized in seen:
                continue
            seen.add(normalized)
            addresses.append(address)
        return addresses

    @staticmethod
    def _new_smtp_copy_id() -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"OASK-SENT-{timestamp}-{uuid4().hex[:8]}"

    @staticmethod
    def _split_addresses(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]

    def move_to_folder(self, message: OutlookMessage, folder_name: str) -> None:
        """Mark a processed message read, then move it to its source store."""
        if message.raw_item is None:
            logger.warning("Move skipped because raw Outlook item is missing.")
            return

        target = folder_name.strip().lower()
        destination = None
        if target in {"deleted", "deleted items"}:
            parent = getattr(message.raw_item, "Parent", None)
            source_store = getattr(parent, "Store", None)
            if source_store is not None:
                try:
                    destination = source_store.GetDefaultFolder(
                        self.OL_FOLDER_DELETED_ITEMS
                    )
                except Exception:
                    logger.warning(
                        "Could not resolve Deleted Items from the source store; "
                        "using shared mailbox lookup."
                    )

        if destination is None:
            destination = self._get_mailbox_folder(folder_name)

        was_unread = bool(getattr(message.raw_item, "UnRead", False))
        if was_unread:
            message.raw_item.UnRead = False
            message.raw_item.Save()

        try:
            moved_item = message.raw_item.Move(destination)
        except Exception:
            if was_unread:
                message.raw_item.UnRead = True
                message.raw_item.Save()
            raise

        if moved_item is not None and bool(
            getattr(moved_item, "UnRead", False)
        ):
            moved_item.UnRead = False
            moved_item.Save()
        logger.info(
            "Marked Outlook message read and moved it to %s in its source mailbox.",
            folder_name,
        )

    def _get_source_folder(self) -> Any:
        if self.source_folder.lower() == "inbox":
            try:
                store = self._get_mailbox_store()
                return store.GetDefaultFolder(self.OL_FOLDER_INBOX)
            except RuntimeError:
                return self._get_shared_default_folder(self.OL_FOLDER_INBOX)

        return self._get_mailbox_folder(self.source_folder)

    def _get_mailbox_folder(self, folder_name: str) -> Any:
        target = folder_name.strip().lower()
        if target in {"deleted", "deleted items"}:
            try:
                store = self._get_mailbox_store()
                return store.GetDefaultFolder(self.OL_FOLDER_DELETED_ITEMS)
            except RuntimeError:
                return self._get_shared_default_folder(
                    self.OL_FOLDER_DELETED_ITEMS
                )

        try:
            root = self._get_mailbox_store().GetRootFolder()
        except RuntimeError:
            root = self._get_shared_default_folder(self.OL_FOLDER_INBOX).Parent

        for folder in root.Folders:
            if str(folder.Name).strip().lower() == target:
                return folder

        raise RuntimeError(
            f"Folder '{folder_name}' not found in mailbox {self.mailbox_smtp}."
        )

    def _get_mailbox_store(self) -> Any:
        if self._namespace is None:
            raise RuntimeError("Outlook namespace is not connected.")

        for store in self._namespace.Stores:
            smtp = self._store_smtp(store)
            display_name = str(getattr(store, "DisplayName", "") or "").lower()

            if smtp == self.mailbox_smtp or self.mailbox_smtp in display_name:
                return store

        raise RuntimeError(
            f"Mailbox SMTP not found in Outlook profile: {self.mailbox_smtp}"
        )

    def _get_shared_default_folder(self, folder_type: int) -> Any:
        if self._namespace is None:
            raise RuntimeError("Outlook namespace is not connected.")

        recipient = self._namespace.CreateRecipient(self.mailbox_smtp)
        if not recipient.Resolve():
            raise RuntimeError(
                "Shared mailbox address could not be resolved in Outlook: "
                f"{self.mailbox_smtp}"
            )
        try:
            return self._namespace.GetSharedDefaultFolder(
                recipient,
                folder_type,
            )
        except Exception as error:
            raise RuntimeError(
                "Shared mailbox folder cannot be accessed: "
                f"{self.mailbox_smtp}. Check Full Access permission."
            ) from error

    def _store_smtp(self, store: Any) -> str:
        try:
            account = store.GetDefaultFolder(self.OL_FOLDER_INBOX).Store
            return str(getattr(account, "DisplayName", "") or "").lower()
        except Exception:
            return str(getattr(store, "DisplayName", "") or "").lower()

    def _save_attachments(
        self,
        item: Any,
        output_folder: Path,
    ) -> list[OutlookAttachment]:
        attachments: list[OutlookAttachment] = []
        count = int(getattr(item.Attachments, "Count", 0) or 0)

        for index in range(1, count + 1):
            attachment = item.Attachments.Item(index)
            file_name = str(getattr(attachment, "FileName", "") or "")
            if not file_name:
                continue

            safe_name = self._safe_attachment_name(file_name)
            file_path = self._unique_path(output_folder / safe_name)
            attachment.SaveAsFile(str(file_path))
            attachments.append(OutlookAttachment(file_name=file_name, path=file_path))

        return attachments

    def _get_sender_email(self, item: Any) -> str:
        try:
            sender = item.Sender
            if sender is not None:
                exchange_user = sender.GetExchangeUser()
                if exchange_user is not None:
                    return str(exchange_user.PrimarySmtpAddress or "").lower()
        except Exception:
            pass

        value = str(getattr(item, "SenderEmailAddress", "") or "")
        return value.strip().lower()

    def _get_cc_emails(self, item: Any) -> str:
        """Resolve CC recipients to SMTP addresses instead of display names."""
        emails: list[str] = []

        try:
            recipients = item.Recipients
            count = int(getattr(recipients, "Count", 0) or 0)
            for index in range(1, count + 1):
                recipient = recipients.Item(index)
                if int(getattr(recipient, "Type", 0) or 0) != 2:
                    continue

                email = self._recipient_smtp_address(recipient)
                if email and email not in emails:
                    emails.append(email)
        except Exception:
            logger.warning(
                "Unable to resolve Outlook CC recipients; using display value."
            )

        if emails:
            return "; ".join(emails)

        return str(getattr(item, "CC", "") or "").strip().lower()

    @staticmethod
    def _recipient_smtp_address(recipient: Any) -> str:
        """Return a recipient's SMTP address across SMTP and Exchange types."""
        direct_address = str(getattr(recipient, "Address", "") or "").strip()
        if "@" in direct_address:
            return direct_address.lower()

        address_entry = getattr(recipient, "AddressEntry", None)
        if address_entry is None:
            return ""

        try:
            exchange_user = address_entry.GetExchangeUser()
            if exchange_user is not None:
                value = str(
                    getattr(exchange_user, "PrimarySmtpAddress", "") or ""
                ).strip()
                if value:
                    return value.lower()
        except Exception:
            pass

        entry_address = str(
            getattr(address_entry, "Address", "") or ""
        ).strip()
        if "@" in entry_address:
            return entry_address.lower()

        try:
            value = str(
                address_entry.PropertyAccessor.GetProperty(
                    "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
                )
                or ""
            ).strip()
            if value:
                return value.lower()
        except Exception:
            pass

        return ""

    def _find_account(self, smtp: str) -> Any:
        if self._namespace is None:
            return None

        smtp_lower = smtp.strip().lower()
        try:
            for account in self._namespace.Accounts:
                account_smtp = str(getattr(account, "SmtpAddress", "") or "").lower()
                if account_smtp == smtp_lower:
                    return account
        except Exception:
            logger.warning("Unable to inspect Outlook accounts.")

        return None

    @staticmethod
    def _safe_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        return None

    @staticmethod
    def _safe_attachment_name(value: str) -> str:
        return "".join(
            character
            if character not in '<>:"/\\|?*'
            else "_"
            for character in value
        )

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        for index in range(2, 1000):
            candidate = parent / f"{stem}_{index}{suffix}"
            if not candidate.exists():
                return candidate

        raise RuntimeError(f"Unable to create unique attachment path for {path}")
