from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from ui.context import AppContext
from ui.pages.dashboard_page import DashboardPage
from ui.services.dashboard_service import (
    ActivityItem,
    BackupSummary,
    DashboardSummary,
    ModuleSummary,
)
from ui.services.system_health_service import HealthStatus, HealthSummary


class _ImmediateRunner:
    def submit(self, function, *, on_done, **kwargs):
        try:
            result = SimpleNamespace(success=True, value=function(), error=None)
        except Exception as exc:
            result = SimpleNamespace(success=False, value=None, error=str(exc))
        on_done(result)
        return object()


class _DashboardService:
    def __init__(self) -> None:
        self.calls = 0

    def get_dashboard_summary(self):
        self.calls += 1
        return DashboardSummary(
            True,
            "Healthy",
            "READY",
            BackupSummary(False),
            "NOT_CHECKED",
            (ModuleSummary("ATTENDANCE", total=6),),
            (),
        )


def _page(tk_root, tmp_path, *, health_summary):
    dashboard_service = _DashboardService()
    services = SimpleNamespace(
        dashboard_service=dashboard_service,
        system_health_service=SimpleNamespace(get_summary=lambda: health_summary),
        task_runner=_ImmediateRunner(),
        dialog_service=SimpleNamespace(error=lambda *args, **kwargs: None),
        file_system_service=SimpleNamespace(open_folder=lambda *args, **kwargs: False),
    )
    context = AppContext(
        tmp_path,
        tmp_path / "assets",
        "ui-dashboard-test",
        logging.getLogger("ui-dashboard-test"),
        app_services=services,
    )
    return DashboardPage(tk_root, context), dashboard_service


def test_dashboard_uses_session_system_health_after_explicit_check(
    tk_root, tmp_path
) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.WARNING, "2026-07-29T10:00:00"),
    )

    page.on_show()
    tk_root.update_idletasks()

    assert page.summary_cards["System Health"].value_label.cget("text") == "Warning"


def test_dashboard_refreshes_each_time_it_is_shown(tk_root, tmp_path) -> None:
    page, dashboard_service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )

    page.on_show()
    page.on_show()

    assert dashboard_service.calls == 2


def test_dashboard_summary_values_use_smooth_blink_styles(tk_root, tmp_path) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )

    page.on_show()
    page._stop_value_blink()
    page._advance_value_blink()

    assert (
        page.summary_cards["Database Status"].value_label.cget("style")
        == "DashboardValue.TLabel"
    )
    assert (
        page.module_cards["ATTENDANCE"].value_label.cget("style")
        == "DashboardValueBlink1.TLabel"
    )

    page.on_hide()

    assert (
        page.summary_cards["Database Status"].value_label.cget("style")
        == "DashboardValue.TLabel"
    )
    assert (
        page.module_cards["ATTENDANCE"].value_label.cget("style")
        == "DashboardValue.TLabel"
    )


def test_module_activity_detail_labels_use_status_colors(tk_root, tmp_path) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )
    card = page.module_cards["ATTENDANCE"]

    card.set_summary(
        ModuleSummary(
            "ATTENDANCE",
            total=7,
            succeeded=6,
            failed=1,
            last_status="COMPLETED_WITH_WARNING",
        )
    )

    assert card.success_label.cget("style") == "ModuleSuccess.TLabel"
    assert card.failure_label.cget("style") == "ModuleError.TLabel"
    assert card.status_label.cget("style") == "ModuleWarning.TLabel"


def test_dashboard_retro_chomper_starts_and_stops_with_page(
    tk_root, tmp_path
) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )

    page.on_show()
    page.chomper_canvas.configure(width=240)
    page._draw_chomper()

    assert page._chomper_job is not None
    assert page.chomper_canvas.find_withtag("chomper")

    page.on_hide()

    assert page._chomper_job is None
    assert not page.chomper_canvas.find_withtag("chomper")


def test_dashboard_retro_chomper_eats_and_resets_pellets(tk_root, tmp_path) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )
    page.on_show()
    page.chomper_canvas.configure(width=60)

    page._advance_chomper()

    assert page._chomper_eaten_until > -1

    page._chomper_x = 87
    page._advance_chomper()

    assert page._chomper_x == 0
    assert page._chomper_eaten_until == 0


def test_recent_activity_rows_use_status_font_color_tags(tk_root, tmp_path) -> None:
    page, _service = _page(
        tk_root,
        tmp_path,
        health_summary=HealthSummary((), HealthStatus.NOT_CHECKED, None),
    )
    page._render(
        DashboardSummary(
            True,
            "Healthy",
            "READY",
            BackupSummary(False),
            "NOT_CHECKED",
            (),
            (
                ActivityItem(
                    1,
                    "2026-07-29T10:00:00",
                    "ATTENDANCE",
                    None,
                    "COMPLETED",
                    Path("out"),
                ),
                ActivityItem(
                    2,
                    "2026-07-29T10:01:00",
                    "UTILITIES",
                    None,
                    "COMPLETED_WITH_WARNING",
                    None,
                ),
                ActivityItem(3, "2026-07-29T10:02:00", "HRIS", None, "FAILED", None),
                ActivityItem(
                    4,
                    "2026-07-29T10:03:00",
                    "OUTLOOK_REVISI",
                    None,
                    "RUNNING",
                    None,
                ),
            ),
        )
    )

    rows = page.table.get_children()

    assert page.table.item(rows[0], "tags") == ("activity_success",)
    assert page.table.item(rows[1], "tags") == ("activity_warning",)
    assert page.table.item(rows[2], "tags") == ("activity_error",)
    assert page.table.item(rows[3], "tags") == ("activity_running",)
