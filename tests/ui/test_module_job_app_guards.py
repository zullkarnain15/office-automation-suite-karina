from __future__ import annotations

from types import SimpleNamespace

from ui.app import OASKUnifiedApp
from ui.pages.attendance_ot_page import AttendanceOTPage
from ui.services.module_job_coordinator import ModuleJobCoordinator


def _active_coordinator(tmp_path):
    coordinator = ModuleJobCoordinator()
    coordinator.try_start(
        "ATTENDANCE", "Attendance", write_paths=(tmp_path / "Attendance",)
    )
    return coordinator


def test_application_close_is_blocked_for_hidden_active_job(tmp_path) -> None:
    warnings = []
    messages = []
    app = object.__new__(OASKUnifiedApp)
    app._closing = False
    app.context = SimpleNamespace(
        app_services=SimpleNamespace(
            module_job_coordinator=_active_coordinator(tmp_path),
            dialog_service=SimpleNamespace(
                warning=lambda *args: warnings.append(args)
            ),
        )
    )
    app.status_bar = SimpleNamespace(set_message=messages.append)

    assert not app.close()
    assert warnings and "Attendance" in warnings[0][1]
    assert messages == ["Penutupan dibatalkan: job masih berjalan"]


def test_attendance_ot_write_is_blocked_while_module_job_runs(tmp_path) -> None:
    warnings = []
    page = object.__new__(AttendanceOTPage)
    page._busy = False
    page._disposed = False
    page.services = SimpleNamespace(
        module_job_coordinator=_active_coordinator(tmp_path),
        dialog_service=SimpleNamespace(warning=lambda *args: warnings.append(args)),
    )

    result = page.run_task(
        lambda: None,
        lambda value: None,
        "Update ATT&OT",
        lock_navigation=True,
    )

    assert result is None and not page._busy
    assert warnings and "Attendance" in warnings[0][1]
