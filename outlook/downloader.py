"""
Outlook Object Model integration for Outlook - Revisi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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


class OutlookComClient:
    """Thin wrapper around Microsoft Outlook COM automation."""

    OL_FOLDER_INBOX = 6

    def __init__(
        self,
        mailbox_smtp: str,
        source_folder: str = "Inbox",
        reply_from_smtp: str | None = None,
    ) -> None:
        self.mailbox_smtp = mailbox_smtp.strip().lower()
        self.source_folder = source_folder.strip() or "Inbox"
        self.reply_from_smtp = (reply_from_smtp or mailbox_smtp).strip().lower()
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

    def move_to_folder(self, message: OutlookMessage, folder_name: str) -> None:
        """Move original message after reply has been sent/drafted."""
        if message.raw_item is None:
            logger.warning("Move skipped because raw Outlook item is missing.")
            return

        destination = self._get_mailbox_folder(folder_name)
        message.raw_item.Move(destination)

    def _get_source_folder(self) -> Any:
        if self.source_folder.lower() == "inbox":
            store = self._get_mailbox_store()
            return store.GetDefaultFolder(self.OL_FOLDER_INBOX)

        return self._get_mailbox_folder(self.source_folder)

    def _get_mailbox_folder(self, folder_name: str) -> Any:
        store = self._get_mailbox_store()
        root = store.GetRootFolder()
        target = folder_name.strip().lower()

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
