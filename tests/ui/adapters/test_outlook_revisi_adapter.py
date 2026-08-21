from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from outlook.downloader import OutlookComClient
from outlook.engine import OutlookRevisiEngine
from shared.config_manager import OutlookRevisiConfigurationReader
from ui.adapters.outlook_revisi_adapter import OutlookRevisiAdapter
from ui.outlook_revisi_models import (
    OutlookRevisiCancellationToken,
    OutlookRevisiResolvedRequest,
)


def _sheet(book, name: str, headers: list[str], row: list[str]) -> None:
    sheet = book.create_sheet(name)
    sheet.append(headers)
    sheet.append(row)


def workbook(
    path: Path,
    *,
    mailbox: str = "karina.hr.1@oto.co.id",
    folder: str = "Inbox",
    unknown_placeholder: bool = False,
) -> Path:
    book = Workbook()
    general = book.active
    general.title = "General"
    general.append(["Parameter", "Value", "Description"])
    for key, value in (
        ("Mailbox_SMTP", mailbox),
        ("Source_Folder", folder),
        ("Reply_From_SMTP", mailbox),
        ("Send_Transport", "OUTLOOK"),
        ("Output_Root", str(path.parent / "legacy-output")),
        ("Payroll_Period", "01-2020"),
        ("Auto_Reply_Enabled", "TRUE"),
        ("Send_Mode", "SEND"),
        ("PIC_HR_Emails", "pic@example.com"),
        ("SPV_PIC_HR_Emails", "spv@example.com"),
    ):
        general.append([key, value, ""])
    _sheet(
        book,
        "HO_Sender_Master",
        ["Active", "Sender_Name", "Sender_Email", "Required_CC_Email"],
        ["Y", "HO", "ho@example.com", "cc@example.com"],
    )
    _sheet(
        book,
        "Branch_Sender_Master",
        [
            "Active",
            "Company",
            "Branch_Code",
            "Sender_Name",
            "Sender_Email",
            "Required_CC_Email",
        ],
        ["Y", "OTO", "AMU", "Branch", "branch@example.com", "cc@example.com"],
    )
    _sheet(
        book,
        "Subject_Rules",
        ["Active", "Workflow", "Subject_Pattern"],
        ["Y", "All", "ATT {PERIOD}"],
    )
    _sheet(
        book,
        "Attachment_Rules",
        ["Active", "Workflow", "Allowed_Extensions"],
        ["Y", "All", ".xlsx;.txt"],
    )
    _sheet(
        book,
        "Validation_Rules",
        ["Active", "Rule_Code", "Workflow", "Rule_Value"],
        ["Y", "NIK_REQUIRED", "All", "TRUE"],
    )
    body = "Line one\nLine two {SENDER_NAME}"
    if unknown_placeholder:
        body += "\n{UNKNOWN_TOKEN}"
    _sheet(
        book,
        "Reply_Templates",
        [
            "Active",
            "Reply_Code",
            "Recipient_Type",
            "Trigger",
            "Subject_Template",
            "Body_Template",
        ],
        ["Y", "SUCCESS_SENDER", "SENDER", "PROCESS_SUCCESS", "Re: {PERIOD}", body],
    )
    book.save(path)
    return path


def resolved(config: Path, output: Path, *, workflow: str = "HO", dry_run=True):
    return OutlookRevisiResolvedRequest(
        "UI-OUTLOOK-TEST",
        None,
        config,
        workflow,
        output,
        "2026-07-01",
        "2026-07-31",
        "07-2026",
        False,
        False,
        dry_run,
        25,
    )


class ReadyClient:
    def validate_mailbox(self):
        return "RPA.HR01", "Inbox"


def test_configuration_rule_template_and_mailbox_preview(tmp_path: Path) -> None:
    config = workbook(tmp_path / "outlook.xlsx", unknown_placeholder=True)
    adapter = OutlookRevisiAdapter(client_factory=lambda configuration: ReadyClient())

    result = adapter.validate(resolved(config, tmp_path), check_mailbox=True)

    assert result.valid and result.mailbox.valid
    assert result.sender_count == 1
    assert result.subject_rule_count == result.attachment_rule_count == 1
    assert result.template_previews[0][2] == (
        "Line one\nLine two {SENDER_NAME}\n{UNKNOWN_TOKEN}"
    )
    assert any("UNKNOWN_TOKEN" in warning for warning in result.warnings)
    assert result.outbound.effective_mode == "PREVIEW"
    assert not result.outbound.requires_confirmation


def test_wrong_mailbox_and_folder_are_blocked_without_com(tmp_path: Path) -> None:
    config = workbook(
        tmp_path / "wrong.xlsx",
        mailbox="someone@example.com",
        folder="Other",
    )
    calls = []
    adapter = OutlookRevisiAdapter(
        client_factory=lambda configuration: calls.append(configuration)
    )

    result = adapter.validate(resolved(config, tmp_path), check_mailbox=True)

    assert not result.valid
    assert calls == []
    assert any("karina.hr.1@oto.co.id" in error for error in result.errors)
    assert any("Inbox" in error for error in result.errors)


def test_outlook_unavailable_is_structured_and_does_not_crash(tmp_path: Path) -> None:
    config = workbook(tmp_path / "outlook.xlsx")

    class Unavailable:
        def validate_mailbox(self):
            raise RuntimeError("Outlook Classic unavailable")

    result = OutlookRevisiAdapter(
        client_factory=lambda configuration: Unavailable()
    ).validate(resolved(config, tmp_path), check_mailbox=True)

    assert not result.valid
    assert result.mailbox.outlook_status == "UNAVAILABLE"
    assert "Outlook Classic unavailable" in result.mailbox.error


def test_live_send_mode_requires_outbound_confirmation(tmp_path: Path) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    adapter = OutlookRevisiAdapter(client_factory=lambda configuration: ReadyClient())

    result = adapter.validate(
        resolved(config, tmp_path, dry_run=False), check_mailbox=False
    )

    assert result.outbound.auto_reply_enabled
    assert result.outbound.send_mode == "SEND"
    assert result.outbound.effective_mode == "SEND"
    assert result.outbound.requires_confirmation


def test_engine_receives_runtime_output_period_and_normalizes_files(
    tmp_path: Path,
) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    output = tmp_path / "manual-output"
    received = {}

    class Engine:
        def __init__(self, **values):
            received.update(values)

        def run(self):
            runtime = OutlookRevisiConfigurationReader(
                received["configuration_file"]
            ).read()
            assert runtime.get_output_root() == output
            assert runtime.general["Payroll_Period"] == "07-2026"
            received["progress_callback"]("READING_INBOX", "Reading Inbox")
            folder = output / "HO" / "job"
            attachments = folder / "Attachments"
            attachments.mkdir(parents=True)
            txt = folder / "attendance.txt"
            report = folder / "report.xlsx"
            process_log = folder / "Process.log"
            summary = folder / "summary.json"
            for item in (txt, report, process_log, summary):
                item.touch()
            message = SimpleNamespace(
                attachment_count=1,
                attachment_results=[SimpleNamespace(file_status="ACCEPTED")],
                reply_result="NOT_ATTEMPTED",
                output_files=[txt],
            )
            return SimpleNamespace(
                success=True,
                cancelled=False,
                output_folder=folder,
                total_email=1,
                target_email=1,
                success_email=1,
                failed_email=0,
                skipped_other_workflow=0,
                message_results=[message],
                process_log=process_log,
                summary_json=summary,
                report_file=report,
                anomaly_row_count=0,
                reconciliation_issues=[],
            )

    events = []
    result = OutlookRevisiAdapter(
        engine_class=Engine,
        client_factory=lambda configuration: ReadyClient(),
    ).run(
        resolved(config, output),
        cancellation=OutlookRevisiCancellationToken(),
        progress=events.append,
        log=events.append,
    )

    assert result.success and result.message_counts["success"] == 1
    assert {item.file_type for item in result.output_files} == {
        "OUTPUT_FOLDER",
        "ATTACHMENT_FOLDER",
        "HRIS_TXT",
        "EXCEL_REPORT",
        "PROCESS_LOG",
        "SUMMARY_JSON",
    }
    staged = output / "HRIS" / "HO" / "attendance.txt"
    assert staged.exists()
    assert (output / "HO" / "job" / "attendance.txt").exists()
    assert not received["configuration_file"].exists()
    assert events


def test_outlook_module_root_stages_hris_txt_to_shared_output_root(
    tmp_path: Path,
) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    shared_output = tmp_path / "output"
    output = shared_output / "Outlook-Revisi"

    class Engine:
        def __init__(self, **_values):
            pass

        def run(self):
            folder = output / "HO" / "job"
            attachments = folder / "Attachments"
            attachments.mkdir(parents=True)
            txt = folder / "attendance.txt"
            txt.write_text('"001","07/01/2026","08:00","","",""\n', encoding="utf-8")
            report = folder / "report.xlsx"
            process_log = folder / "Process.log"
            summary = folder / "summary.json"
            for item in (report, process_log, summary):
                item.touch()
            message = SimpleNamespace(
                attachment_count=1,
                attachment_results=[SimpleNamespace(file_status="ACCEPTED")],
                reply_result="NOT_ATTEMPTED",
                output_files=[txt],
            )
            return SimpleNamespace(
                success=True,
                cancelled=False,
                output_folder=folder,
                total_email=1,
                target_email=1,
                success_email=1,
                failed_email=0,
                skipped_other_workflow=0,
                message_results=[message],
                process_log=process_log,
                summary_json=summary,
                report_file=report,
                anomaly_row_count=0,
                reconciliation_issues=[],
            )

    result = OutlookRevisiAdapter(
        engine_class=Engine,
        client_factory=lambda configuration: ReadyClient(),
    ).run(
        resolved(config, output),
        cancellation=OutlookRevisiCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )

    assert result.success
    assert (shared_output / "HRIS" / "HO" / "attendance.txt").exists()
    assert not (output / "HRIS").exists()


def test_partial_batch_is_warning_and_stages_successful_txt(
    tmp_path: Path,
) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    output = tmp_path / "manual-output"

    class Engine:
        def __init__(self, **_values):
            pass

        def run(self):
            folder = output / "HO" / "job"
            folder.mkdir(parents=True)
            txt = folder / "attendance.txt"
            report = folder / "report.xlsx"
            process_log = folder / "Process.log"
            summary = folder / "summary.json"
            for item in (txt, report, process_log, summary):
                item.touch()
            successful = SimpleNamespace(
                attachment_count=2,
                attachment_results=[
                    SimpleNamespace(file_status="WARNING"),
                    SimpleNamespace(file_status="IGNORED_UNSUPPORTED"),
                ],
                reply_result="SENT",
                output_files=[txt],
            )
            failed = SimpleNamespace(
                attachment_count=1,
                attachment_results=[SimpleNamespace(file_status="FAILED")],
                reply_result="NOT_ATTEMPTED",
                output_files=[],
            )
            return SimpleNamespace(
                success=False,
                cancelled=False,
                output_folder=folder,
                total_email=2,
                target_email=2,
                success_email=1,
                failed_email=1,
                skipped_other_workflow=0,
                message_results=[successful, failed],
                process_log=process_log,
                summary_json=summary,
                report_file=report,
                anomaly_row_count=0,
                reconciliation_issues=[],
            )

    result = OutlookRevisiAdapter(
        engine_class=Engine,
        client_factory=lambda configuration: ReadyClient(),
    ).run(
        resolved(config, output),
        cancellation=OutlookRevisiCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )

    assert result.success
    assert result.warning_count == 1
    assert result.error_summary == "1 email gagal diproses."
    assert result.message_counts == {
        "total": 2,
        "target": 2,
        "success": 1,
        "failed": 1,
        "skipped": 0,
    }
    assert result.attachment_counts == {
        "total": 3,
        "accepted": 1,
        "rejected": 1,
        "ignored": 1,
        "skipped": 0,
    }
    assert (output / "HRIS" / "HO" / "attendance.txt").exists()


def test_cancellation_before_connect_never_constructs_engine(tmp_path: Path) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    calls = []
    token = OutlookRevisiCancellationToken()
    token.request()

    result = OutlookRevisiAdapter(
        engine_class=lambda **values: calls.append(values)
    ).run(
        resolved(config, tmp_path),
        cancellation=token,
        progress=lambda event: None,
        log=lambda event: None,
    )

    assert result.cancelled and calls == []


def test_store_display_name_cannot_impersonate_target_mailbox() -> None:
    store = SimpleNamespace(
        DisplayName="karina.hr.1@oto.co.id - unverified display",
        PropertyAccessor=None,
        GetRootFolder=lambda: SimpleNamespace(PropertyAccessor=None),
        StoreID="store",
    )
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace(Stores=[store], Accounts=[])

    try:
        client._get_mailbox_store()
    except RuntimeError as exc:
        assert "Mailbox SMTP not found" in str(exc)
    else:
        raise AssertionError("DisplayName must never satisfy SMTP selection")


def test_store_exact_smtp_property_is_accepted() -> None:
    accessor = SimpleNamespace(GetProperty=lambda name: "karina.hr.1@oto.co.id")
    store = SimpleNamespace(PropertyAccessor=accessor, StoreID="store")
    client = OutlookComClient("karina.hr.1@oto.co.id")
    client._namespace = SimpleNamespace(Stores=[store], Accounts=[])

    assert client._get_mailbox_store() is store


def test_engine_cancellation_after_inbox_read_stops_before_message_and_outbound(
    tmp_path: Path,
) -> None:
    config = workbook(tmp_path / "outlook.xlsx")
    cancelled = [False]
    outbound_calls = []

    class Client:
        def fetch_messages(self, **kwargs):
            cancelled[0] = True
            return [SimpleNamespace(entry_id="must-not-process")]

        def send_reply(self, **kwargs):
            outbound_calls.append("reply")

        def send_mail(self, **kwargs):
            outbound_calls.append("summary")

    events = []
    result = OutlookRevisiEngine(
        config,
        "HO",
        dry_run=False,
        client=Client(),
        progress_callback=lambda stage, message: events.append(stage),
        cancellation_requested=lambda: cancelled[0],
    ).run()

    assert result.cancelled and not result.success
    assert result.message_results == []
    assert result.final_status == "CANCELLED"
    assert outbound_calls == []
    assert {"CONNECTING_OUTLOOK", "RESOLVING_MAILBOX", "READING_INBOX"} <= set(events)
