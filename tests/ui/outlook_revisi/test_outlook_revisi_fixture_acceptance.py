from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.database import REQUIRED_TABLES, SchemaManager, SQLiteConnectionFactory
from shared.database.repositories import GlobalSettingsRepository
from shared.storage import get_database_path
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.adapters.outlook_revisi_adapter import OutlookRevisiAdapter
from ui.app import OASKUnifiedApp
from ui.context import AppContext
from ui.services.outlook_revisi_service import OutlookRevisiService
from ui.services.service_container import build_default_app_services


def _sheet(book, name: str, headers: list[str], row: list[str]) -> None:
    sheet = book.create_sheet(name)
    sheet.append(headers)
    sheet.append(row)


def _workbook(path: Path, output: Path) -> Path:
    book = Workbook()
    general = book.active
    general.title = "General"
    general.append(["Parameter", "Value", "Description"])
    for key, value in (
        ("Mailbox_SMTP", "karina.hr.1@oto.co.id"),
        ("Source_Folder", "Inbox"),
        ("Reply_From_SMTP", "karina.hr.1@oto.co.id"),
        ("Send_Transport", "OUTLOOK"),
        ("Output_Root", str(output)),
        ("Payroll_Period", "07-2026"),
        ("Auto_Reply_Enabled", "TRUE"),
        ("Send_Mode", "SEND"),
        ("PIC_HR_Emails", ""),
        ("SPV_PIC_HR_Emails", ""),
    ):
        general.append([key, value, "fixture"])
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
        [
            "Y",
            "SUCCESS_SENDER",
            "SENDER",
            "PROCESS_SUCCESS",
            "Re: {ORIGINAL_SUBJECT}",
            "Line one\nLine two {SENDER_NAME}",
        ],
    )
    book.save(path)
    return path


class _ReadyClient:
    def validate_mailbox(self):
        return "RPA.HR01", "Inbox"


class _FixtureEngine:
    mode = "success"

    def __init__(self, **values) -> None:
        self.values = values

    def run(self):
        if self.mode == "failed":
            raise RuntimeError("fixture engine failure")
        output = Path(
            self.values["configuration_file"]
        )  # Runtime workbook must exist during engine invocation.
        assert output.exists()
        configuration = (
            __import__(
                "shared.config_manager", fromlist=["OutlookRevisiConfigurationReader"]
            )
            .OutlookRevisiConfigurationReader(output)
            .read()
        )
        root = configuration.get_output_root()
        folder = root / self.values["workflow"] / f"fixture-{time.time_ns()}"
        attachments = folder / "Attachments"
        attachments.mkdir(parents=True)
        txt = folder / "attendance.txt"
        report = folder / "report.xlsx"
        process_log = folder / "Process.log"
        summary = folder / "summary.json"
        for item in (txt, report, process_log, summary):
            item.touch()
        self.values["progress_callback"]("READING_INBOX", "Reading Inbox fixture")
        time.sleep(0.12)
        cancelled = self.values["cancellation_requested"]()
        reply_result = (
            "CANCELLED"
            if cancelled
            else "NOT_ATTEMPTED"
            if self.values["dry_run"]
            else "SENT"
        )
        message = SimpleNamespace(
            attachment_count=1,
            attachment_results=[SimpleNamespace(file_status="ACCEPTED")],
            reply_result=reply_result,
            output_files=[txt],
        )
        return SimpleNamespace(
            success=not cancelled,
            cancelled=cancelled,
            output_folder=folder,
            total_email=1,
            target_email=1,
            success_email=0 if cancelled else 1,
            failed_email=0,
            skipped_other_workflow=0,
            message_results=[message],
            process_log=process_log,
            summary_json=summary,
            report_file=report,
            anomaly_row_count=0,
            reconciliation_issues=[],
        )


def _wait(root, predicate, timeout: float = 5.0) -> int:
    deadline = time.monotonic() + timeout
    ticks = 0
    while time.monotonic() < deadline:
        root.update()
        ticks += 1
        if predicate():
            return ticks
        time.sleep(0.01)
    raise AssertionError("Timed out while pumping the Tk event loop.")


def test_safe_fixture_manual_acceptance(tmp_path: Path) -> None:
    if os.environ.get("OASK_UI5_ACCEPTANCE_CHILD") != "1":
        environment = dict(os.environ)
        environment["OASK_UI5_ACCEPTANCE_CHILD"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                f"{__file__}::test_safe_fixture_manual_acceptance",
                "-q",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout
        return

    tk_root = tk.Tk()
    tk_root.withdraw()
    data_root = tmp_path / "Data"
    database = get_database_path(data_root)
    database.parent.mkdir(parents=True)
    SchemaManager().initialize_database(database, "ui5-acceptance")
    output = tmp_path / "FixtureOutput"
    with SQLiteConnectionFactory().connect(database) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(output),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.execute(
            "INSERT INTO outlook_settings ("
            "outlook_settings_id, use_global_output, use_global_period, "
            "mailbox_smtp, payroll_period, updated_at"
            ") VALUES (1, 1, 0, 'karina.hr.1@oto.co.id', "
            "'07-2026', '2026-07-01')"
        )
    configuration = _workbook(tmp_path / "Outlook-Fixture.xlsx", output)
    backend = FakeRegistryBackend()
    registry = StorageRegistryService(backend)
    registry.write_storage_pointer(data_root, database)
    services = build_default_app_services(
        tk_root,
        application_version=APP_VERSION,
        project_root=PROJECT_ROOT,
        registry=registry,
        default_data_root=data_root,
    )
    services.outlook_revisi_service = OutlookRevisiService(
        services.storage_service,
        OutlookRevisiAdapter(
            engine_class=_FixtureEngine,
            client_factory=lambda config: _ReadyClient(),
        ),
    )
    confirmations = []
    typed = []
    opened = []
    services.dialog_service = type(
        "Dialog",
        (),
        {
            "select_file": lambda self, **values: configuration,
            "select_folder": lambda self, **values: output,
            "confirm": lambda self, title, message: (
                confirmations.append(message) or True
            ),
            "typed_confirm": lambda self, title, message, expected: (
                typed.append(expected) or True
            ),
            "warning": lambda *args: None,
            "error": lambda *args: None,
        },
    )()
    services.file_system_service = type(
        "FileSystem",
        (),
        {"open_folder": lambda self, path: opened.append(Path(path)) or True},
    )()
    context = AppContext(
        PROJECT_ROOT,
        PROJECT_ROOT / "assets",
        APP_VERSION,
        logging.getLogger("ui5.fixture-acceptance"),
        app_services=services,
    )
    app = OASKUnifiedApp(tk_root, context=context)
    assert app.navigate("outlook_revisi")
    page = app.navigation._cache["outlook_revisi"]
    _wait(tk_root, lambda: page._defaults_loaded and not page._busy)
    assert page.global_output_var.get()
    assert page.payroll_period_var.get() == "07-2026"
    assert page.dry_run_var.get()
    page.browse_configuration()
    page.global_output_var.set(False)
    page._apply_global_state()
    page.output_var.set(str(output))

    page.validate_configuration()
    _wait(tk_root, lambda: not page._busy)
    assert "Line one / Line two" in page.validation_summary.label.cget("text")
    page.validate_mailbox()
    _wait(tk_root, lambda: not page._busy)
    assert "Outlook: READY" in page.mailbox_status_var.get()
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0] == 0
    assert not output.exists()

    for workflow in ("HO", "BRANCH"):
        page.workflow_var.set(workflow)
        page.validate_configuration()
        _wait(tk_root, lambda: not page._busy)
        assert f"Workflow: {workflow}" in page.validation_summary.label.cget("text")

    page.workflow_var.set("HO")
    page.run_outlook()
    _wait(tk_root, lambda: page._running)
    responsive_ticks = _wait(tk_root, lambda: not page._running)
    assert page._last_result.success and responsive_ticks > 2
    assert typed == []
    page.open_output()
    page.open_attachments()
    page.open_process_log()

    page.dry_run_var.set(False)
    page.outbound_ack_var.set(True)
    page.workflow_var.set("BRANCH")
    page.run_outlook()
    _wait(tk_root, lambda: page._running)
    _wait(tk_root, lambda: not page._running)
    assert page._last_result.success and typed == ["SEND"]

    page.dry_run_var.set(True)
    page.outbound_ack_var.set(False)
    page.workflow_var.set("HO")
    page.run_outlook()
    _wait(tk_root, lambda: page._running)
    _wait(
        tk_root,
        lambda: "Reading Inbox fixture" in page.progress.label.cget("text"),
    )
    page.cancel()
    _wait(tk_root, lambda: not page._running)
    assert page._last_result.cancelled and page.can_navigate_away()

    _FixtureEngine.mode = "failed"
    page.run_outlook()
    _wait(tk_root, lambda: page._running)
    _wait(tk_root, lambda: not page._running)
    assert not page._last_result.success
    assert "FAILED" in page.result_summary.label.cget("text")
    _FixtureEngine.mode = "success"

    assert app.navigate("history")
    _wait(
        tk_root,
        lambda: (
            app.navigation.active_page_id == "history"
            and not app.navigation._cache["history"]._busy
        ),
    )
    assert app.navigate("dashboard")
    _wait(
        tk_root,
        lambda: (
            app.navigation.active_page_id == "dashboard"
            and not app.navigation._cache["dashboard"]._busy
        ),
    )
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        statuses = [
            row[0]
            for row in connection.execute(
                "SELECT unified_status FROM job_history "
                "WHERE module_code='OUTLOOK_REVISI' ORDER BY job_pk"
            )
        ]
        file_count = connection.execute("SELECT COUNT(*) FROM job_files").fetchone()[0]
        outbound_events = connection.execute(
            "SELECT COUNT(*) FROM job_status_events WHERE phase='OUTBOUND_CONFIRMED'"
        ).fetchone()[0]
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    assert statuses == ["COMPLETED", "COMPLETED", "CANCELLED", "FAILED"]
    assert file_count == 18
    assert outbound_events == 1
    assert table_count == len(REQUIRED_TABLES)
    assert len(confirmations) == 4
    assert len(opened) == 3
    assert backend.write_count == 1  # Explicit Fake Registry setup only.
    assert backend.delete_count == 0
    assert app.close()
    services.task_runner.shutdown()
