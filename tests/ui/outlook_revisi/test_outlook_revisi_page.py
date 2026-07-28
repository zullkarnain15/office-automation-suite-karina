from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

from config.app_config import PROJECT_ROOT
from ui.context import AppContext
from ui.outlook_revisi_models import (
    MailboxValidationResult,
    OutboundSafetyState,
    OutlookRevisiLogEvent,
    OutlookRevisiProgressEvent,
    OutlookRevisiResolvedRequest,
    OutlookRevisiRunResult,
    OutlookRevisiValidationResult,
)
from ui.pages.outlook_revisi_page import OutlookRevisiPage


def test_page_construction_has_no_outlook_workbook_database_or_output_action(
    tk_root,
) -> None:
    calls = []
    services = SimpleNamespace(
        outlook_revisi_service=SimpleNamespace(
            load_defaults=lambda: calls.append("defaults"),
            preflight=lambda *args, **kwargs: calls.append("preflight"),
        ),
        task_runner=SimpleNamespace(
            submit=lambda *args, **kwargs: calls.append("task")
        ),
        dialog_service=SimpleNamespace(),
        file_system_service=SimpleNamespace(),
    )
    context = AppContext(
        PROJECT_ROOT,
        PROJECT_ROOT / "assets",
        "ui5",
        logging.getLogger("ui5"),
        app_services=services,
    )
    page = OutlookRevisiPage(tk_root, context)
    tk_root.update_idletasks()
    assert calls == []
    assert page.dry_run_var.get()
    assert not page._running
    assert not page.manual_fallback_var.get()
    assert page._request().configuration_path is None


def test_page_never_imports_outlook_engine_or_com_directly() -> None:
    path = PROJECT_ROOT / "ui" / "pages" / "outlook_revisi_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {
        node.module.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "outlook" not in roots
    source = path.read_text(encoding="utf-8")
    assert "win32com" not in source and "pythoncom" not in source
    assert 'text="Outlook Revisi Configuration"' not in source
    assert "Konfigurasi: OAS-K Database" in source
    assert "Advanced / Manual Fallback" in source


def test_outlook_revisi_uses_compact_attendance_style_layout() -> None:
    source = (
        PROJECT_ROOT / "ui" / "pages" / "outlook_revisi_page.py"
    ).read_text(encoding="utf-8")
    assert "ResponsiveCardGrid" not in source
    assert "ModernCard" not in source
    assert "CompactPanel.TFrame" in source
    assert "CompactProgress" in source
    assert 'text="Start"' in source
    assert "Process Log" in source


def test_manual_fallback_is_session_only_and_clears_when_disabled(tk_root) -> None:
    services = SimpleNamespace(
        outlook_revisi_service=SimpleNamespace(),
        task_runner=SimpleNamespace(),
        dialog_service=SimpleNamespace(),
        file_system_service=SimpleNamespace(),
    )
    context = AppContext(
        PROJECT_ROOT,
        PROJECT_ROOT / "assets",
        "ui5b",
        logging.getLogger("ui5b-outlook-fallback"),
        app_services=services,
    )
    page = OutlookRevisiPage(tk_root, context)
    page.manual_fallback_var.set(True)
    page._toggle_fallback()
    page.config_var.set("temporary.xlsx")
    page.manual_fallback_var.set(False)
    page._toggle_fallback()
    assert page.config_var.get() == ""


def test_navigation_is_blocked_only_while_running() -> None:
    page = object.__new__(OutlookRevisiPage)
    page._running = False
    assert page.can_navigate_away() and page.can_close()
    page._running = True
    assert not page.can_navigate_away() and not page.can_close()


class _ImmediateRunner:
    def submit(self, function, *, on_done, **kwargs):
        try:
            result = SimpleNamespace(success=True, value=function(), error=None)
        except Exception as exc:
            result = SimpleNamespace(success=False, value=None, error=str(exc))
        on_done(result)
        return object()

    def submit_reporting(self, function, *, on_done, on_progress, **kwargs):
        try:
            value = function(on_progress)
            result = SimpleNamespace(success=True, value=value, error=None)
        except Exception as exc:
            result = SimpleNamespace(success=False, value=None, error=str(exc))
        on_done(result)
        return object()


class _Service:
    def __init__(self, tmp_path: Path, *, live: bool) -> None:
        self.tmp_path = tmp_path
        self.live = live
        self.preflight_calls = []
        self.confirm_calls = []
        self.run_calls = []

    def preflight(self, request, *, require_database, check_mailbox):
        self.preflight_calls.append((require_database, check_mailbox))
        resolved = OutlookRevisiResolvedRequest(
            "UI-OUTLOOK-FIXTURE",
            self.tmp_path / "OAS-K.db",
            request.configuration_path,
            request.workflow,
            request.override_output_root,
            "2026-07-01",
            "2026-07-31",
            "07-2026",
            request.use_global_output,
            request.use_global_period,
            request.dry_run,
            request.message_limit,
            self.live,
        )
        safety = OutboundSafetyState(
            True,
            "SEND",
            "SEND" if self.live else "PREVIEW",
            True,
            False,
            requires_confirmation=self.live,
        )
        value = OutlookRevisiValidationResult(
            True,
            True,
            request.workflow,
            resolved.period_start,
            resolved.period_end,
            resolved.output_root,
            MailboxValidationResult(
                True,
                "karina.hr.1@oto.co.id",
                "Inbox",
                "READY",
                True,
                True,
                "RPA.HR01",
            ),
            safety,
            sender_count=1,
            subject_rule_count=1,
            attachment_rule_count=1,
            validation_rule_count=1,
            reply_template_count=1,
            template_previews=(("SUCCESS", "Re", "Line 1\nLine 2"),),
        )
        return resolved, value

    def confirm_outbound(self, resolved, safety, *, acknowledged, typed_confirmed):
        self.confirm_calls.append((acknowledged, typed_confirmed))
        return resolved

    def run_job(self, resolved, *, progress, log, **kwargs):
        self.run_calls.append(resolved.job_id)
        progress(OutlookRevisiProgressEvent("READING_INBOX", "Reading Inbox"))
        log(OutlookRevisiLogEvent("2026-07-01", "INFO", "Fixture log"))
        return OutlookRevisiRunResult(
            True,
            False,
            resolved.job_id,
            resolved.workflow,
            "karina.hr.1@oto.co.id",
            "2026-07-01T00:00:00+00:00",
            "2026-07-01T00:00:01+00:00",
            resolved.output_root,
            None,
            {"total": 1, "success": 1, "failed": 0},
            {"total": 1},
            {"sent": 0, "drafted": 0},
            (),
        )


def _interactive_page(tk_root, tmp_path: Path, *, live=False, typed=True, final=True):
    service = _Service(tmp_path, live=live)
    confirmations = []
    typed_calls = []
    warnings = []
    services = SimpleNamespace(
        outlook_revisi_service=service,
        task_runner=_ImmediateRunner(),
        dialog_service=SimpleNamespace(
            confirm=lambda title, message: confirmations.append(message) or final,
            typed_confirm=lambda title, message, expected: (
                typed_calls.append(expected) or typed
            ),
            warning=lambda *args: warnings.append(args),
            select_file=lambda **kwargs: None,
            select_folder=lambda **kwargs: None,
        ),
        file_system_service=SimpleNamespace(open_folder=lambda path: False),
    )
    context = AppContext(
        tmp_path,
        tmp_path / "assets",
        "ui5",
        logging.getLogger("ui5-interaction"),
        app_services=services,
    )
    page = OutlookRevisiPage(tk_root, context)
    config = tmp_path / "Outlook.xlsx"
    config.touch()
    page.config_var.set(str(config))
    page.payroll_period_var.set("07-2026")
    page.output_var.set(str(tmp_path / "output"))
    page.dry_run_var.set(not live)
    return page, service, confirmations, typed_calls, warnings


def test_preview_confirmation_precedes_job_and_streams_result(
    tk_root, tmp_path: Path
) -> None:
    page, service, confirmations, typed_calls, _ = _interactive_page(tk_root, tmp_path)

    page.run_outlook()

    assert confirmations and not typed_calls
    assert service.preflight_calls == [(True, True)]
    assert service.run_calls == ["UI-OUTLOOK-FIXTURE"]
    assert not page._busy and not page._running and page.can_navigate_away()
    assert "Fixture log" in page.log_text.get("1.0", "end")
    assert page._last_result.success


def test_live_send_requires_checkbox_typed_send_and_second_confirmation(
    tk_root, tmp_path: Path
) -> None:
    page, service, confirmations, typed_calls, warnings = _interactive_page(
        tk_root, tmp_path, live=True
    )
    page.run_outlook()
    assert warnings and not typed_calls and not confirmations and not service.run_calls

    page.outbound_ack_var.set(True)
    page.run_outlook()

    assert typed_calls == ["SEND"]
    assert confirmations
    assert service.confirm_calls == [(True, True)]
    assert service.run_calls == ["UI-OUTLOOK-FIXTURE"]


def test_declined_typed_or_final_confirmation_never_creates_job(
    tk_root, tmp_path: Path
) -> None:
    page, service, _, typed_calls, _ = _interactive_page(
        tk_root, tmp_path, live=True, typed=False
    )
    page.outbound_ack_var.set(True)
    page.run_outlook()
    assert typed_calls == ["SEND"] and not service.run_calls

    page, service, confirmations, _, _ = _interactive_page(
        tk_root, tmp_path, live=False, final=False
    )
    page.run_outlook()
    assert confirmations and not service.run_calls


def test_failed_background_task_restores_busy_navigation(
    tk_root, tmp_path: Path
) -> None:
    page, service, _, _, _ = _interactive_page(tk_root, tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeError("fixture worker failed")

    service.run_job = fail
    page.run_outlook()
    assert not page._busy and not page._running and page.can_navigate_away()
