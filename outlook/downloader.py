"""
Outlook Object Model integration for Outlook - Revisi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
import smtplib
from typing import Any
from typing import Callable

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


class OutlookComClient:
    """Thin wrapper around Microsoft Outlook COM automation."""

    OL_FOLDER_INBOX = 6
    OL_FOLDER_DELETED_ITEMS = 3
    OL_FOLDER_SENT_MAIL = 5

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

            message = OutlookMessage(
                entry_id=str(getattr(item, "EntryID", "") or ""),
                store_id=str(getattr(item, "Parent", "").StoreID)
                if getattr(item, "Parent", None) is not None
                else "",
                subject=str(getattr(item, "Subject", "") or ""),
                sender_name=str(getattr(item, "SenderName", "") or ""),
                sender_email=self._get_sender_email(item),
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
    ) -> None:
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
            self._send_smtp(
                to=[to or message.sender_email],
                cc=self._split_addresses(cc),
                subject=subject,
                body=body,
                send_mode=send_mode,
                headers=headers,
            )
            return

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
    ) -> None:
        """Send mail through the trusted internal SMTP relay."""
        if send_mode.strip().upper() == "DRAFT":
            raise RuntimeError(
                "Send_Mode DRAFT is not supported when Send_Transport is SMTP."
            )
        if not self.smtp_server:
            raise RuntimeError("SMTP_Server is required for SMTP transport.")
        if not self.reply_from_smtp or "@" not in self.reply_from_smtp:
            raise RuntimeError("Reply_From_SMTP must be a valid email address.")

        recipients = [item.strip() for item in [*to, *cc] if item.strip()]
        if not recipients:
            raise RuntimeError("SMTP message has no recipients.")

        mail = EmailMessage()
        mail["From"] = self.reply_from_smtp
        mail["To"] = "; ".join(item.strip() for item in to if item.strip())
        if cc:
            mail["Cc"] = "; ".join(item.strip() for item in cc if item.strip())
        mail["Subject"] = subject
        for name, value in (headers or {}).items():
            if value:
                mail[name] = value
        mail.set_content(body)

        with smtplib.SMTP(
            self.smtp_server,
            self.smtp_port,
            timeout=self.smtp_timeout,
        ) as smtp:
            smtp.send_message(mail, to_addrs=recipients)

        logger.info(
            "Email sent through SMTP relay %s:%s from %s.",
            self.smtp_server,
            self.smtp_port,
            self.reply_from_smtp,
        )

        if self.save_smtp_copy_to_sent:
            self._save_smtp_sent_copy(
                to=to,
                cc=cc,
                subject=subject,
                body=body,
            )

    def _save_smtp_sent_copy(
        self,
        to: list[str],
        cc: list[str],
        subject: str,
        body: str,
    ) -> None:
        """Archive a best-effort copy of an SMTP message in Outlook Sent Items."""
        try:
            if self._outlook is None or self._namespace is None:
                self.connect()

            destination = self._get_sent_items_folder()
            copy = self._outlook.CreateItem(0)
            copy.To = "; ".join(item.strip() for item in to if item.strip())
            copy.CC = "; ".join(item.strip() for item in cc if item.strip())
            copy.Subject = subject
            copy.Body = body
            copy.Save()
            copy.Move(destination)
            logger.info(
                "SMTP sent copy archived in Outlook Sent Items for mailbox %s.",
                self.mailbox_smtp,
            )
        except Exception:
            # SMTP delivery has already succeeded. Archiving must never cause a
            # retry because that could send a duplicate reply.
            logger.exception(
                "SMTP delivery succeeded, but its Outlook Sent Items copy "
                "could not be archived."
            )

    def _get_sent_items_folder(self) -> Any:
        """Resolve shared-mailbox Sent Items, then fall back to profile default."""
        try:
            return self._get_mailbox_store().GetDefaultFolder(
                self.OL_FOLDER_SENT_MAIL
            )
        except Exception:
            logger.warning(
                "Could not resolve shared mailbox Sent Items from its store; "
                "trying shared-folder access."
            )

        try:
            return self._get_shared_default_folder(self.OL_FOLDER_SENT_MAIL)
        except Exception:
            logger.warning(
                "Could not access shared mailbox Sent Items; using the "
                "default Outlook profile Sent Items folder."
            )

        if self._namespace is None:
            raise RuntimeError("Outlook namespace is not connected.")
        return self._namespace.GetDefaultFolder(self.OL_FOLDER_SENT_MAIL)

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
