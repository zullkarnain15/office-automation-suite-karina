from types import SimpleNamespace
from unittest.mock import patch

from outlook.downloader import OutlookComClient


class _Recipients:
    def __init__(self, recipients) -> None:
        self._recipients = recipients
        self.Count = len(recipients)

    def Item(self, index: int):
        return self._recipients[index - 1]


def test_cc_resolver_uses_smtp_address_instead_of_display_name() -> None:
    cc_recipient = SimpleNamespace(
        Type=2,
        Name="Kiyan Resto",
        Address="kiyanresto@gmail.com",
        AddressEntry=None,
    )
    to_recipient = SimpleNamespace(
        Type=1,
        Name="Mailbox",
        Address="mailbox@example.com",
        AddressEntry=None,
    )
    item = SimpleNamespace(
        CC="Kiyan Resto",
        Recipients=_Recipients([to_recipient, cc_recipient]),
    )
    client = OutlookComClient("mailbox@example.com")

    assert client._get_cc_emails(item) == "kiyanresto@gmail.com"


def test_cc_resolver_falls_back_to_mailitem_cc_value() -> None:
    item = SimpleNamespace(CC="cc@example.com", Recipients=_Recipients([]))
    client = OutlookComClient("mailbox@example.com")

    assert client._get_cc_emails(item) == "cc@example.com"


def test_smtp_reply_uses_configured_from_and_thread_headers() -> None:
    raw_item = SimpleNamespace(InternetMessageID="<source-message@example.com>")
    message = SimpleNamespace(
        raw_item=raw_item,
        sender_email="sender@example.com",
    )
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        reply_from_smtp="karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
        smtp_port=25,
        save_smtp_copy_to_sent=False,
    )

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        client.send_reply(
            message=message,
            subject="Re: Attendance",
            body="Processed",
            to="sender@example.com",
            cc="pic@example.com; supervisor@example.com",
        )

    smtp_class.assert_called_once_with("mail.oto.co.id", 25, timeout=30)
    sent = smtp_class.return_value.__enter__.return_value.send_message.call_args
    mail = sent.args[0]
    assert mail["From"] == "karina.hr.1@oto.co.id"
    assert mail["In-Reply-To"] == "<source-message@example.com>"
    assert mail["References"] == "<source-message@example.com>"
    assert sent.kwargs["to_addrs"] == [
        "sender@example.com",
        "pic@example.com",
        "supervisor@example.com",
    ]


def test_smtp_success_archives_copy_in_shared_sent_items() -> None:
    sent_items = SimpleNamespace(Name="Sent Items")
    moved_to = []
    archived = SimpleNamespace()
    archived.Save = lambda: None
    archived.Move = lambda destination: moved_to.append(destination)
    outlook = SimpleNamespace(CreateItem=lambda _item_type: archived)
    store = SimpleNamespace(
        GetDefaultFolder=lambda folder_type: (
            sent_items if folder_type == 5 else None
        )
    )
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )
    client._outlook = outlook
    client._namespace = SimpleNamespace()
    client._get_mailbox_store = lambda: store

    with patch("outlook.downloader.smtplib.SMTP"):
        client.send_mail(
            ["sender@example.com"],
            ["cc@example.com"],
            "Reply subject",
            "Reply body",
        )

    assert archived.To == "sender@example.com"
    assert archived.CC == "cc@example.com"
    assert archived.Subject == "Reply subject"
    assert archived.Body == "Reply body"
    assert moved_to == [sent_items]


def test_sent_copy_failure_does_not_resend_or_fail_smtp_delivery() -> None:
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )
    client.connect = lambda: (_ for _ in ()).throw(RuntimeError("COM failed"))

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        client.send_mail(["sender@example.com"], [], "Subject", "Body")

    smtp = smtp_class.return_value.__enter__.return_value
    smtp.send_message.assert_called_once()


def test_smtp_transport_rejects_draft_mode() -> None:
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )

    try:
        client.send_mail([], [], "Subject", "Body", send_mode="DRAFT")
    except RuntimeError as error:
        assert "DRAFT is not supported" in str(error)
    else:
        raise AssertionError("SMTP transport must reject DRAFT mode")


def test_shared_mailbox_inbox_fallback_resolves_smtp_address() -> None:
    shared_inbox = SimpleNamespace(Name="Inbox")
    recipient = SimpleNamespace(Resolve=lambda: True)
    namespace = SimpleNamespace(
        Stores=[],
        CreateRecipient=lambda address: (
            recipient if address == "karina.hr.1@oto.co.id" else None
        ),
        GetSharedDefaultFolder=lambda resolved, folder_type: (
            shared_inbox
            if resolved is recipient and folder_type == 6
            else None
        ),
    )
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = namespace

    assert client._get_source_folder() is shared_inbox


def test_move_to_deleted_items_uses_message_source_store() -> None:
    deleted_items = SimpleNamespace(Name="Deleted Items")
    source_store = SimpleNamespace(
        GetDefaultFolder=lambda folder_type: (
            deleted_items if folder_type == 3 else None
        )
    )
    moved_to = []
    saved_states = []
    raw_item = SimpleNamespace(Parent=SimpleNamespace(Store=source_store))
    raw_item.UnRead = True
    raw_item.Save = lambda: saved_states.append(raw_item.UnRead)
    raw_item.Move = lambda destination: moved_to.append(destination)
    message = SimpleNamespace(raw_item=raw_item)
    client = OutlookComClient("karina.hr.1@oto.co.id")

    client.move_to_folder(message, "Deleted")

    assert moved_to == [deleted_items]
    assert raw_item.UnRead is False
    assert saved_states == [False]


def test_move_failure_restores_unread_status() -> None:
    deleted_items = SimpleNamespace(Name="Deleted Items")
    source_store = SimpleNamespace(GetDefaultFolder=lambda _type: deleted_items)
    saved_states = []
    raw_item = SimpleNamespace(Parent=SimpleNamespace(Store=source_store))
    raw_item.UnRead = True
    raw_item.Save = lambda: saved_states.append(raw_item.UnRead)

    def fail_move(_destination):
        raise RuntimeError("move denied")

    raw_item.Move = fail_move
    message = SimpleNamespace(raw_item=raw_item)
    client = OutlookComClient("karina.hr.1@oto.co.id")

    try:
        client.move_to_folder(message, "Deleted")
    except RuntimeError as error:
        assert str(error) == "move denied"
    else:
        raise AssertionError("Move failure must be propagated")

    assert raw_item.UnRead is True
    assert saved_states == [False, True]
