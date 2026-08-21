from types import SimpleNamespace
from unittest.mock import patch

from outlook.downloader import OutlookComClient
from outlook.downloader import SmtpSentCopyResult
from outlook.engine import OutlookProcessMessageResult
from outlook.engine import OutlookRevisiEngine


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


def test_smtp_reply_bcc_uses_mailbox_without_visible_bcc_header() -> None:
    message = SimpleNamespace(
        raw_item=SimpleNamespace(InternetMessageID="<source@example.com>"),
        sender_email="sender@example.com",
    )
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        copy_result = client.send_reply(
            message,
            "Re: Reply subject",
            "Reply body",
            cc="cc@example.com",
        )

    sent = smtp_class.return_value.__enter__.return_value.send_message.call_args
    mail = sent.args[0]
    assert sent.kwargs["to_addrs"] == [
        "sender@example.com",
        "cc@example.com",
        "karina.hr.1@oto.co.id",
    ]
    assert mail["Bcc"] is None
    assert mail["X-OAS-K-Copy-ID"] == copy_result.copy_id
    assert copy_result.status == "BCC_ACCEPTED"


def test_smtp_bcc_uses_mailbox_smtp_not_reply_from_smtp() -> None:
    message = SimpleNamespace(
        raw_item=SimpleNamespace(InternetMessageID="<source@example.com>"),
        sender_email="sender@example.com",
    )
    client = OutlookComClient(
        "archive.mailbox@oto.co.id",
        reply_from_smtp="smtp.sender@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        client.send_reply(message, "Re: Attendance", "Processed")

    sent = smtp_class.return_value.__enter__.return_value.send_message.call_args
    assert sent.args[0]["From"] == "smtp.sender@oto.co.id"
    assert sent.kwargs["to_addrs"] == [
        "sender@example.com",
        "archive.mailbox@oto.co.id",
    ]


def test_smtp_summary_mail_does_not_create_bcc_archive() -> None:
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        client.send_mail(
            ["pic@example.com"],
            ["supervisor@example.com"],
            "Process summary",
            "Completed",
        )

    sent = smtp_class.return_value.__enter__.return_value.send_message.call_args
    assert sent.kwargs["to_addrs"] == [
        "pic@example.com",
        "supervisor@example.com",
    ]
    assert sent.args[0]["X-OAS-K-Copy-ID"] is None


def test_bcc_rejection_does_not_resend_or_fail_smtp_delivery() -> None:
    message = SimpleNamespace(
        raw_item=SimpleNamespace(InternetMessageID="<source@example.com>"),
        sender_email="sender@example.com",
    )
    client = OutlookComClient(
        "karina.hr.1@oto.co.id",
        send_transport="SMTP",
        smtp_server="mail.oto.co.id",
    )

    with patch("outlook.downloader.smtplib.SMTP") as smtp_class:
        smtp = smtp_class.return_value.__enter__.return_value
        smtp.send_message.return_value = {
            "karina.hr.1@oto.co.id": (550, b"BCC rejected")
        }
        copy_result = client.send_reply(message, "Subject", "Body")

    smtp.send_message.assert_called_once()
    assert copy_result.status == "BCC_REJECTED"
    assert "550" in copy_result.detail


class _Items:
    def __init__(self, items) -> None:
        self._items = items
        self.Count = len(items)

    def Sort(self, *_args) -> None:
        return None

    def Item(self, index: int):
        return self._items[index - 1]

    def __iter__(self):
        return iter(self._items)


def test_bcc_archive_moves_from_source_store_to_sent_items() -> None:
    copy_id = "OASK-SENT-TEST-001"
    sent_items = SimpleNamespace(Name="Sent Items")
    moved_to = []
    saved_states = []
    store = SimpleNamespace()
    item = SimpleNamespace(
        Class=43,
        Subject="Re: Attendance",
        InternetMessageID=f"<{copy_id}@oto.co.id>",
        PropertyAccessor=SimpleNamespace(
            GetProperty=lambda _name: f"X-OAS-K-Copy-ID: {copy_id}\r\n"
        ),
        Parent=SimpleNamespace(Store=store),
        UnRead=True,
    )
    item.Save = lambda: saved_states.append(item.UnRead)
    item.Move = lambda destination: moved_to.append(destination)
    inbox = SimpleNamespace(Items=_Items([item]))
    store.GetDefaultFolder = lambda folder_type: {
        5: sent_items,
        6: inbox,
    }.get(folder_type)

    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace()
    client._get_mailbox_store = lambda: store
    client.register_pending_smtp_copy(copy_id)

    result = client.collect_smtp_sent_copies(
        {copy_id},
        timeout_seconds=0,
    )[copy_id]

    assert result.status == "MOVED_TO_SENT"
    assert moved_to == [sent_items]
    assert saved_states == [False]


def test_missing_bcc_archive_remains_pending_without_resend() -> None:
    copy_id = "OASK-SENT-TEST-002"
    inbox = SimpleNamespace(Items=_Items([]))
    store = SimpleNamespace(
        GetDefaultFolder=lambda folder_type: inbox if folder_type == 6 else None
    )
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace()
    client._get_mailbox_store = lambda: store
    client.register_pending_smtp_copy(copy_id)

    result = client.collect_smtp_sent_copies(
        {copy_id},
        timeout_seconds=0,
    )[copy_id]

    assert result.status == "COPY_PENDING"


def test_bcc_archive_is_excluded_from_normal_inbox_processing(tmp_path) -> None:
    copy_id = "OASK-SENT-TEST-003"
    item = SimpleNamespace(
        Class=43,
        Subject="Re: Attendance",
        SenderEmailAddress="karina.hr.1@oto.co.id",
        PropertyAccessor=SimpleNamespace(
            GetProperty=lambda _name: f"X-OAS-K-Copy-ID: {copy_id}\r\n"
        ),
        Parent=SimpleNamespace(StoreID="store"),
        Attachments=SimpleNamespace(Count=0),
    )
    inbox = SimpleNamespace(Items=_Items([item]))
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace()
    client._get_source_folder = lambda: inbox

    messages = client.fetch_messages(tmp_path)

    assert messages == []


def test_bcc_move_failure_leaves_copy_pending_for_retry() -> None:
    copy_id = "OASK-SENT-TEST-004"
    sent_items = SimpleNamespace(Name="Sent Items")
    store = SimpleNamespace()
    item = SimpleNamespace(
        Class=43,
        Subject="Re: Attendance",
        PropertyAccessor=SimpleNamespace(
            GetProperty=lambda _name: f"X-OAS-K-Copy-ID: {copy_id}\r\n"
        ),
        Parent=SimpleNamespace(Store=store),
        UnRead=False,
        Move=lambda _destination: (_ for _ in ()).throw(
            RuntimeError("move denied")
        ),
    )
    inbox = SimpleNamespace(Items=_Items([item]))
    store.GetDefaultFolder = lambda folder_type: {
        5: sent_items,
        6: inbox,
    }.get(folder_type)
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace()
    client._get_mailbox_store = lambda: store
    client.register_pending_smtp_copy(copy_id)

    result = client.collect_smtp_sent_copies(
        {copy_id},
        timeout_seconds=0,
    )[copy_id]

    assert result.status == "MOVE_FAILED"
    assert result.detail == "move denied"


def test_engine_collects_bcc_status_and_persists_only_pending(tmp_path) -> None:
    moved_id = "OASK-SENT-MOVED"
    pending_id = "OASK-SENT-PENDING"
    records = {
        moved_id: SmtpSentCopyResult(
            copy_id=moved_id,
            status="MOVED_TO_SENT",
            detail="moved",
        ),
        pending_id: SmtpSentCopyResult(
            copy_id=pending_id,
            status="COPY_PENDING",
            detail="waiting",
        ),
    }
    calls = []
    client = SimpleNamespace(
        collect_smtp_sent_copies=lambda ids, **kwargs: (
            calls.append((ids, kwargs)) or records
        ),
        get_smtp_copy_result=lambda copy_id: records.get(copy_id),
    )
    results = [
        OutlookProcessMessageResult(
            entry_id=copy_id,
            subject=f"Subject {copy_id}",
            sender_email="sender@example.com",
            workflow="HO",
            status="SUCCESS",
            errors=[],
            output_files=[],
            reply_sent=True,
            sent_copy_id=copy_id,
            sent_copy_status="BCC_ACCEPTED",
        )
        for copy_id in (moved_id, pending_id)
    ]
    engine = OutlookRevisiEngine("unused.xlsx", "HO")

    pending = engine._collect_smtp_sent_copies(client, results)
    engine._save_pending_sent_copies(tmp_path, "HO", pending)
    loaded = engine._load_pending_sent_copies(tmp_path, "HO")

    assert calls == [
        (
            {moved_id, pending_id},
            {"timeout_seconds": 5, "poll_interval": 1},
        )
    ]
    assert results[0].sent_copy_status == "MOVED_TO_SENT"
    assert results[1].sent_copy_status == "COPY_PENDING"
    assert set(loaded) == {pending_id}


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
