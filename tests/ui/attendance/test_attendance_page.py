from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

from config.app_config import PROJECT_ROOT
from ui.context import AppContext
from ui.attendance_models import (
    AttendanceLogEvent,
    AttendanceProgressEvent,
    AttendanceResolvedRequest,
    AttendanceRunResult,
    AttendanceValidationResult,
)
from ui.pages.attendance_page import AttendancePage
from ui.constants import BUTTON_FONT, SIDEBAR_WIDTH


def test_page_construction_has_no_engine_workbook_or_storage_action(tk_root) -> None:
    calls = []
    services = SimpleNamespace(
        attendance_service=SimpleNamespace(
            load_defaults=lambda: calls.append("defaults"),
            adapter=SimpleNamespace(
                validate_configuration=lambda value: calls.append("workbook")
            ),
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
        "ui4",
        logging.getLogger("ui4"),
        app_services=services,
    )
    page = AttendancePage(tk_root, context)
    tk_root.update_idletasks()
    assert calls == []
    assert not page._running
    assert not page.manual_fallback_var.get()
    assert page._request().configuration_path is None


def test_page_never_imports_engine_directly() -> None:
    path = PROJECT_ROOT / "ui" / "pages" / "attendance_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = {
        node.module.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "attendance" not in roots
    source = path.read_text(encoding="utf-8")
    assert 'text="Attendance Configuration"' not in source
    assert "Konfigurasi: OAS-K Database" in source
    assert "Advanced / Manual Fallback" in source


def test_ui7b1_compact_operational_layout_replaces_card_grid() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "attendance_page.py").read_text(
        encoding="utf-8"
    )
    assert "ResponsiveCardGrid" not in source
    assert "ModernCard" not in source
    assert "Validation & Run" not in source
    assert 'text="Periode"' in source
    assert 'text="Workflow"' in source
    assert 'text="Output"' in source
    assert 'text="Periksa Data"' in source
    assert 'text="Start"' in source
    assert 'load("start_button_pxl.png", size=(120, 48))' in source
    assert 'load("open_folder.ico", size=16)' in source
    assert 'compound="center"' in source


def test_ui7b1_sidebar_and_primary_controls_are_compact() -> None:
    sidebar = (PROJECT_ROOT / "ui" / "widgets" / "sidebar.py").read_text(
        encoding="utf-8"
    )
    styles = (PROJECT_ROOT / "ui" / "style_manager.py").read_text(encoding="utf-8")
    assert SIDEBAR_WIDTH == 230
    assert "Office Automation Suite" not in sidebar
    assert BUTTON_FONT[1] == 8
    assert "font=(ui_family, 10)" in styles
    assert "padding=(9, 7)" in styles


def test_ui7b1_normal_flow_has_no_primary_configuration_or_output_browse() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "attendance_page.py").read_text(
        encoding="utf-8"
    )
    normal_flow = source.split("def _build_advanced", 1)[0]
    assert "Pilih Excel" not in normal_flow
    assert "browse_configuration" not in normal_flow
    assert "browse_output" not in normal_flow
    assert "output_summary_var" in normal_flow


def test_ui7b1_log_result_and_advanced_default_contract() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "attendance_page.py").read_text(
        encoding="utf-8"
    )
    assert "height=5" in source
    assert "Perbesar Log" in source
    assert "self.result_panel.grid_remove()" in source
    assert "self.advanced_frame.grid_remove()" in source
    assert "self.cancel_button.pack_forget()" in source


def test_manual_fallback_is_session_only_and_clears_when_disabled(tk_root) -> None:
    calls = []
    services = SimpleNamespace(
        attendance_service=SimpleNamespace(),
        task_runner=SimpleNamespace(),
        dialog_service=SimpleNamespace(),
        file_system_service=SimpleNamespace(),
    )
    context = AppContext(
        PROJECT_ROOT,
        PROJECT_ROOT / "assets",
        "ui5b",
        logging.getLogger("ui5b-attendance-fallback"),
        app_services=services,
    )
    page = AttendancePage(tk_root, context)
    page.manual_fallback_var.set(True)
    page._toggle_fallback()
    page.config_var.set("temporary.xlsx")
    page.manual_fallback_var.set(False)
    page._toggle_fallback()
    assert page.config_var.get() == ""
    assert calls == []


def test_navigation_is_blocked_only_while_running() -> None:
    page = object.__new__(AttendancePage)
    page._running = False
    assert page.can_navigate_away()
    page._running = True
    assert not page.can_navigate_away()


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


class _AttendanceService:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.preflight_calls = []
        self.run_calls = []

    def preflight(self, request, *, require_database):
        self.preflight_calls.append((request, require_database))
        resolved = AttendanceResolvedRequest(
            "UI-FIXTURE",
            self.tmp_path / "OAS-K.db",
            request.configuration_path,
            request.workflow,
            request.override_output_root,
            request.override_period_start,
            request.override_period_end,
            request.use_global_output,
            request.use_global_period,
            request.generate_txt,
            request.generate_report,
        )
        return resolved, AttendanceValidationResult(
            True,
            True,
            resolved.workflow,
            1,
            resolved.period_start,
            resolved.period_end,
            resolved.output_root,
            resolved.generate_txt,
            resolved.generate_report,
        )

    def run_job(self, resolved, *, progress, log, **kwargs):
        self.run_calls.append(resolved.job_id)
        progress(AttendanceProgressEvent("RUNNING_ENGINE", "Fixture engine stage"))
        log(AttendanceLogEvent("2026-07-01T00:00:00+00:00", "INFO", "Fixture log"))
        return AttendanceRunResult(
            True,
            False,
            resolved.job_id,
            resolved.workflow,
            "2026-07-01T00:00:00+00:00",
            "2026-07-01T00:00:01+00:00",
            resolved.output_root,
            None,
            (),
            {"valid": 1, "anomaly": 0},
        )


def _interactive_page(tk_root, tmp_path: Path, *, confirm: bool):
    attendance = _AttendanceService(tmp_path)
    confirmations = []
    services = SimpleNamespace(
        attendance_service=attendance,
        task_runner=_ImmediateRunner(),
        dialog_service=SimpleNamespace(
            confirm=lambda title, message: confirmations.append(message) or confirm,
            warning=lambda *args: None,
            select_file=lambda **kwargs: None,
            select_folder=lambda **kwargs: None,
        ),
        file_system_service=SimpleNamespace(open_folder=lambda path: False),
    )
    context = AppContext(
        tmp_path,
        tmp_path / "assets",
        "ui4",
        logging.getLogger("ui4-interaction"),
        app_services=services,
    )
    page = AttendancePage(tk_root, context)
    config = tmp_path / "Attendance.xlsx"
    config.touch()
    page.config_var.set(str(config))
    page.start_var.set("07/01/2026")
    page.end_var.set("07/31/2026")
    page.output_var.set(str(tmp_path / "output"))
    return page, attendance, confirmations


def test_confirmation_precedes_job_creation(tk_root, tmp_path: Path) -> None:
    page, attendance, confirmations = _interactive_page(
        tk_root, tmp_path, confirm=False
    )

    page.run_attendance()

    assert confirmations
    assert attendance.preflight_calls[0][1] is True
    assert attendance.run_calls == []


def test_success_restores_busy_navigation_and_streams_result(
    tk_root, tmp_path: Path
) -> None:
    page, attendance, confirmations = _interactive_page(tk_root, tmp_path, confirm=True)

    page.run_attendance()

    assert confirmations and attendance.run_calls == ["UI-FIXTURE"]
    assert not page._busy and not page._running and page.can_navigate_away()
    assert "Fixture log" in page.log_text.get("1.0", "end")
    assert page._last_result.success


def test_failed_background_task_restores_busy_state(tk_root, tmp_path: Path) -> None:
    page, attendance, _ = _interactive_page(tk_root, tmp_path, confirm=True)

    def fail(*args, **kwargs):
        raise RuntimeError("fixture worker failed")

    attendance.run_job = fail
    page.run_attendance()

    assert not page._busy and not page._running and page.can_navigate_away()
