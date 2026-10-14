"""Tk shell contracts for the Sprint 1 Attendance & OT page."""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

from shared.attendance_ot.reporting import MONTHS
from shared.attendance_ot.models import DataUpdateResult
from ui.constants import (
    ATTENDANCE_OT_BACKGROUND,
    ATTENDANCE_OT_CARD,
    ATTENDANCE_OT_CHALK_BLUE,
    ATTENDANCE_OT_CHALK_PINK,
    ATTENDANCE_OT_CHALK_WHITE,
    ATTENDANCE_OT_CHALK_YELLOW,
    ATTENDANCE_OT_SELECTION,
)
from ui.context import AppContext
from ui.pages.attendance_ot_page import AttendanceOTPage
from ui.pages.attendance_ot_widgets import LATE_CELL_HIGH, LATE_CELL_STANDARD


class _Analytics:
    def resolve_status(self):
        return SimpleNamespace(database_exists=False, database_valid=False)


def test_attendance_ot_page_has_six_tabs_and_data_update_actions(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-page-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    page.pack(fill="both", expand=True)
    page.on_show()
    tk_root.update_idletasks()

    assert tuple(
        page.notebook.tab(tab_id, "text") for tab_id in page.notebook.tabs()
    ) == AttendanceOTPage.TAB_TITLES
    assert AttendanceOTPage.TAB_TITLES[-1] == "Data Update"
    update_buttons = {
        child.cget("text")
        for container in page.tabs["Data Update"].winfo_children()
        for child in container.winfo_children()
        if child.winfo_class() == "TButton"
    }
    assert update_buttons == {
        "Update Employee",
        "Update Schedule",
        "Update Attendance & OT",
        "Update All",
    }
    style = ttk.Style(page)
    expected_button_styles = {
        "EMPLOYEE": (
            "AttendanceOTDataUpdateEmployee.TButton",
            page.visual_theme.palette.tab_mint,
        ),
        "SCHEDULE": (
            "AttendanceOTDataUpdateSchedule.TButton",
            page.visual_theme.palette.tab_yellow,
        ),
        "ATTENDANCE_OT": (
            "AttendanceOTDataUpdateAttendance.TButton",
            page.visual_theme.palette.tab_blue,
        ),
    }
    for source_type, button in page.data_update_buttons.items():
        style_name, color = expected_button_styles[source_type]
        assert button.cget("style") == style_name
        assert int(button.cget("width")) == 24
        assert style.lookup(style_name, "background") == color
    assert page.data_update_all_button.cget("style") == (
        "AttendanceOTDataUpdateAll.TButton"
    )
    assert int(page.data_update_all_button.cget("width")) == 24
    assert style.lookup(
        "AttendanceOTDataUpdateAll.TButton", "background"
    ) == page.visual_theme.palette.tab_orange
    assert all(
        label.cget("style") == "AttendanceOTDataUpdatePending.TLabel"
        for label in page.data_update_labels.values()
    )
    assert style.lookup(
        "AttendanceOTDataUpdatePending.TLabel", "foreground"
    ) == page.visual_theme.palette.chalk_muted
    prompt_buttons = {
        child.cget("text")
        for container in page.prompt_frame.winfo_children()
        for child in container.winfo_children()
        if child.winfo_class() == "TButton"
    }
    assert prompt_buttons == {"Create", "Later"}
    assert page.prompt_frame.grid_info()
    assert page.progress_percent_var.get() == "0%"


def test_attendance_ot_progress_bar_shows_color_and_percentage(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-progress-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)

    page._set_refresh_progress(42)

    assert page.progress_percent_var.get() == "42%"
    assert int(float(page.refresh_progress.cget("value"))) == 42
    assert str(page.refresh_progress.cget("mode")) == "determinate"
    assert page.refresh_progress.cget("style") == (
        "AttendanceOT.Horizontal.TProgressbar"
    )
    style = ttk.Style(page)
    assert style.lookup(
        "AttendanceOT.Horizontal.TProgressbar", "background"
    ) == ATTENDANCE_OT_CHALK_BLUE

    page._set_refresh_progress(100, state="success")

    assert page.progress_percent_var.get() == "100%"
    assert page.refresh_progress.cget("style") == (
        "AttendanceOTSuccess.Horizontal.TProgressbar"
    )
    assert style.lookup(
        "AttendanceOTSuccess.Horizontal.TProgressbar", "background"
    ) == page.visual_theme.palette.filter_mint


def test_data_update_pending_indicator_and_database_only_refresh(
    tk_root, tmp_path
) -> None:
    class _Dialog:
        def info(self, *_args):
            pass

        def warning(self, *_args):
            pass

    class _ImporterMustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"Refresh accessed importer method: {name}")

    services = SimpleNamespace(
        attendance_ot_service=_Analytics(),
        attendance_ot_import_service=_ImporterMustNotRun(),
        dialog_service=_Dialog(),
    )
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-data-update-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    page._data_update_completed(
        (
            DataUpdateResult(
                "EMPLOYEE",
                "2026-10-01",
                2,
                50,
                "SUCCESS",
                files_found=2,
                files_new=1,
                files_changed=1,
                files_processed=2,
                rows_inserted=40,
                rows_updated=5,
                rows_unchanged=5,
                duration_seconds=1.25,
            ),
        )
    )
    assert page.data_update_notice.get() == (
        "Data updated — Refresh to view latest data"
    )
    rendered = page.data_update_vars["EMPLOYEE"].get()
    assert "Found: 2" in rendered
    assert "New: 1" in rendered
    assert "Changed: 1" in rendered
    assert "Rows I/U/S: 40/5/5" in rendered
    assert "1.25s" in rendered
    assert page.data_update_labels["EMPLOYEE"].cget("style") == (
        "AttendanceOTDataUpdateComplete.TLabel"
    )
    style = ttk.Style(page)
    assert style.lookup(
        "AttendanceOTDataUpdateComplete.TLabel", "foreground"
    ) == page.visual_theme.palette.filter_mint
    calls = []
    page._invalidate_filter_options = lambda: calls.append("invalidate")
    page.load_view = lambda **kwargs: calls.append(kwargs)

    page.refresh_data()

    assert calls[0] == "invalidate"
    assert calls[1]["options"] is True
    calls[1]["on_success"]()
    assert page.data_update_notice.get() == ""
    assert page.progress_var.get() == "Refresh completed from attendance_ot.db."


def test_attendance_ot_content_uses_shared_application_font(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-font-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    assert page.visual_theme.typography.ui_family in str(
        page.tk.call("ttk::style", "configure", "AttendanceOTBody.TLabel", "-font")
    )


def test_dashboard_kpi_cards_use_their_attendance_icons(tk_root, tmp_path) -> None:
    assets = Path(__file__).resolve().parents[2] / "assets"
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=assets,
        application_version="test",
        logger=logging.getLogger("attendance-ot-kpi-icons-test"),
        app_services=services,
    )

    page = AttendanceOTPage(tk_root, context)
    tk_root.update_idletasks()

    assert set(page.kpi_cards) == {
        "records",
        "employees",
        "late_records",
        "ot_hours",
        "ot_amount",
        "meal_amount",
    }
    for card in page.kpi_cards.values():
        assert card.icon is not None
        assert card.icon_label.cget("image")
        assert card.icon_label.cget("background") == card.body.cget("background")
        assert card.icon_label.pack_info()["side"] == "left"


def test_source_files_tab_has_refresh_and_registry_columns(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-source-tab-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)

    assert page.refresh_button.cget("text") == "Refresh Data"
    assert not hasattr(page, "maintenance_button")
    assert page.duplicate_button.cget("text") == "Cek Duplicate Data"
    assert tuple(page.source_tree.heading(column, "text") for column in page.source_tree["columns"]) == (
        "File",
        "Source Type",
        "Rows",
        "Status",
        "Last Import",
    )


def test_detail_data_tab_uses_display_only_column_order(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-detail-columns-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    table = page.tables["Detail Data"]
    tree = table.tree

    assert tuple(tree["columns"]) == (
        "pay_group",
        "emplid",
        "employee_name",
        "employee_status",
        "date_in",
        "date_out",
        "actual_time_in",
        "actual_time_out",
        "late_status",
        "late_minutes",
        "job_title",
        "branch",
        "department",
        "resolved_schedule_id",
        "resolved_schedule_descr",
        "overtime_hour",
        "overtime_minute",
        "ot_amount",
        "meal_ot_amount",
        "source_file",
    )
    assert tuple(table.heading_labels[column] for column in tree["columns"]) == (
        "Pay Group",
        "EMPLID",
        "Name",
            "Employee Status",
        "Date In",
        "Date Out",
        "Actual In",
        "Actual Out",
        "Attendance Status",
        "Late Minutes",
        "Jabatan",
        "Branch",
        "Department",
        "Schedule ID",
        "Schedule Descr",
        "Overtime Hour",
        "Overtime Minute",
        "OT Amount",
        "Meal OT Amount",
        "Source File",
    )
    assert {
        "resolved_schedule_effdt",
        "scheduled_in",
        "scheduled_out",
    }.isdisjoint(tree["columns"])


def test_detail_data_highlights_actual_and_attendance_headers(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-heading-colors-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    table = page.tables["Detail Data"]

    assert table.header_colors == {}
    assert table.heading_images == {}


def test_attendance_ot_filter_uses_date_pickers_and_iso_boundary(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-date-picker-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    page.date_from_entry.set_iso("2026-09-01")
    page.date_to_entry.set_iso("2026-09-30")
    page.filter_vars["employee_status"].set("Unmapped")

    assert page.multis["divisions"].title == "Division"
    style = ttk.Style(page)
    expected_filter_styles = {
        "branches": (
            "AttendanceOTFilterBranch.TButton",
            page.visual_theme.palette.filter_mint,
        ),
        "pay_groups": (
            "AttendanceOTFilterPayGroup.TButton",
            page.visual_theme.palette.filter_pink,
        ),
        "departments": (
            "AttendanceOTFilterDepartment.TButton",
            page.visual_theme.palette.filter_blue,
        ),
        "divisions": (
            "AttendanceOTFilterDivision.TButton",
            page.visual_theme.palette.filter_purple,
        ),
    }
    for key, (style_name, color) in expected_filter_styles.items():
        assert page.multis[key].button.cget("style") == style_name
        assert style.lookup(style_name, "background") == color

    page.apply_filters()

    assert page.filter_vars["date_from"].get() == "09/01/2026"
    assert page.filter_vars["date_to"].get() == "09/30/2026"
    assert page.filters.date_from == "2026-09-01"
    assert page.filters.date_to == "2026-09-30"
    assert page.filters.employee_status == "Unmapped"
    assert page.date_from_entry.calendar_button.winfo_exists()
    assert page.date_to_entry.calendar_button.winfo_exists()


def test_late_matrix_starts_collapsed_and_colors_the_whole_value_cell(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-late-matrix-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    row = {
        "classification": "HO",
        "group_name": "Finance",
        "emplid": "E001",
        "employee_name": "Karina",
        **{month: 0 for month in MONTHS},
        "Total": 20,
    }
    row["Jan"] = 8
    row["Feb"] = 12
    result = SimpleNamespace(total=1, offset=0, limit=200, items=(row,))

    page._render("Data Terlambat", result, "Employee")

    matrix = page.tables["Data Terlambat"]
    group_key = ("HO", "Finance")
    assert matrix.groups[0]["label"] == "Finance"
    assert matrix.visible_rows == (("group", group_key),)

    matrix.toggle_group(group_key)

    assert matrix.visible_rows == (
        ("group", group_key),
        ("employee", "E001"),
    )
    jan_key = ("employee", "E001", "Jan")
    feb_key = ("employee", "E001", "Feb")
    mar_key = ("employee", "E001", "Mar")
    group_mar_key = ("group", group_key, "Mar")
    assert (
        matrix.canvas.itemcget(matrix.cell_items[jan_key], "fill")
        == LATE_CELL_STANDARD
    )
    assert (
        matrix.canvas.itemcget(matrix.cell_items[feb_key], "fill")
        == LATE_CELL_HIGH
    )
    assert matrix.canvas.itemcget(matrix.cell_text_items[jan_key], "text") == "8"
    assert matrix.canvas.itemcget(matrix.cell_text_items[feb_key], "text") == "12"
    assert mar_key not in matrix.cell_text_items
    assert (
        matrix.canvas.itemcget(matrix.cell_items[mar_key], "fill")
        == ATTENDANCE_OT_CARD
    )
    assert (
        matrix.canvas.itemcget(matrix.cell_items[group_mar_key], "fill")
        == ATTENDANCE_OT_CARD
    )


def test_dashboard_renders_trend_and_two_top_five_bar_lists(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-ranking-cards-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)

    page._render(
        "Dashboard",
        {
            "kpi": {
                "records": 10,
                "employees": 4,
                "late_records": 8,
                "ot_hours": 2,
                "ot_amount": 100,
                "meal_amount": 20,
            },
            "rankings": {
                "HO Employees": (
                    {"emplid": "E001", "employee_name": "Alice", "late_count": 5},
                ),
                "BRANCH Employees": (
                    {"emplid": "E002", "employee_name": "Bob", "late_count": 4},
                ),
                "Branches": ({"branch": "MALILI", "late_count": 5},),
                "HO Departments": ({"department": "Finance", "late_count": 3},),
            },
            "attendance_trend": tuple(value * 10 for value in range(1, 13)),
            "trend": tuple(range(1, 13)),
        },
        "Employee",
    )

    assert tuple(variable.get() for variable in page.trend_panel.value_vars) == tuple(
        str(value) for value in range(1, 13)
    )
    assert tuple(
        variable.get() for variable in page.attendance_trend_panel.value_vars
    ) == tuple(str(value * 10) for value in range(1, 13))
    assert page.dashboard_title.cget("text") == "Attendance & Overtime Overview"
    assert page.dashboard_title.cget("anchor") == "center"
    assert page.dashboard_header.cget("background") == ATTENDANCE_OT_CHALK_WHITE
    assert page.dashboard_header_accent.cget("background") == ATTENDANCE_OT_CHALK_YELLOW
    style = ttk.Style(page)
    assert style.lookup("AttendanceOTPage.TFrame", "background") == (
        ATTENDANCE_OT_BACKGROUND
    )
    assert style.lookup("AttendanceOT.TNotebook.Tab", "background", ("active",)) == (
        ATTENDANCE_OT_CHALK_BLUE
    )
    assert page.apply_button.cget("style") == "AttendanceOTApply.TButton"
    assert page.reset_button.cget("style") == "AttendanceOTReset.TButton"
    assert style.lookup("AttendanceOTApply.TButton", "background") == (
        page.visual_theme.palette.tab_mint
    )
    assert style.lookup("AttendanceOTReset.TButton", "background") == (
        ATTENDANCE_OT_CHALK_PINK
    )
    assert style.lookup("AttendanceOTApply.TButton", "foreground") == (
        ATTENDANCE_OT_CHALK_WHITE
    )
    assert style.lookup("AttendanceOTReset.TButton", "foreground") == (
        ATTENDANCE_OT_CHALK_WHITE
    )
    assert int(page.attendance_trend_panel.grid_info()["row"]) == 2
    assert int(page.trend_panel.grid_info()["row"]) == 3
    assert page.attendance_trend_panel.accent == ATTENDANCE_OT_CHALK_BLUE
    assert page.trend_panel.accent == ATTENDANCE_OT_CHALK_PINK
    assert page.top_department_panel.rows[0]["name"].get() == "Finance"
    assert page.top_department_panel.rows[0]["count"].get() == "3"
    assert page.top_branch_panel.rows[0]["name"].get() == "MALILI"
    assert page.top_branch_panel.rows[0]["count"].get() == "5"
    assert page.kpi_vars["ot_hours"].get() == "2.00"
    assert page.kpi_vars["ot_amount"].get() == "Rp. 100.00"
    assert page.kpi_vars["meal_amount"].get() == "Rp. 20.00"
    assert (
        float(page.top_department_panel.rows[0]["fill"].place_info()["relwidth"])
        == 1.0
    )


def test_dashboard_trend_uses_single_aggregate_read() -> None:
    trend_calls = []
    filters = object()

    class _Session:
        def dashboard(self, received_filters, *, ranking_keys=None):
            assert received_filters is filters
            assert ranking_keys == ("HO Departments", "Branches")
            return {"kpi": {}, "rankings": {}}

        def monthly_trends(self, received_filters, year):
            assert received_filters is filters
            trend_calls.append(year)
            return {
                "attendance": (2, 1, *(0,) * 10),
                "late": (5, 5, *(0,) * 10),
            }

    class _Snapshot:
        def __enter__(self):
            return _Session()

        def __exit__(self, *_args):
            return False

    holder = SimpleNamespace(queries=SimpleNamespace(snapshot=_Snapshot))

    result = AttendanceOTPage._dashboard_view(holder, filters, 2026)

    assert trend_calls == [2026]
    assert result["attendance_trend"][:2] == (2, 1)
    assert result["attendance_trend"][2:] == (0,) * 10
    assert result["trend"][:2] == (5, 5)
    assert result["trend"][2:] == (0,) * 10


def test_filter_options_are_cached_until_analytics_data_changes() -> None:
    calls = []
    choices = {"periods": ("2026-09",)}

    class _Queries:
        def filter_options(self):
            calls.append("filter_options")
            return choices

    holder = SimpleNamespace(queries=_Queries(), _filter_options_cache=None)

    first = AttendanceOTPage._filter_options_for_load(holder)
    second = AttendanceOTPage._filter_options_for_load(holder)
    AttendanceOTPage._invalidate_filter_options(holder)
    refreshed = AttendanceOTPage._filter_options_for_load(holder)

    assert first is second is refreshed is choices
    assert calls == ["filter_options", "filter_options"]


def test_dashboard_kpis_use_balanced_reusable_retro_cards(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-kpi-card-colors-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)

    assert tuple(page.kpi_cards) == (
        "records",
        "employees",
        "late_records",
        "ot_hours",
        "ot_amount",
        "meal_amount",
    )
    primary_cards = {
        key: page.kpi_cards[key]
        for key in ("records", "employees", "late_records")
    }
    assert {key: card.accent for key, card in primary_cards.items()} == {
        "records": ATTENDANCE_OT_CHALK_BLUE,
        "employees": ATTENDANCE_OT_CHALK_YELLOW,
        "late_records": ATTENDANCE_OT_CHALK_PINK,
    }
    assert {
        key: (int(card.grid_info()["row"]), int(card.grid_info()["column"]))
        for key, card in primary_cards.items()
    } == {
        "records": (0, 0),
        "employees": (0, 1),
        "late_records": (0, 2),
    }
    assert {
        key: (int(page.kpi_cards[key].grid_info()["row"]), int(page.kpi_cards[key].grid_info()["column"]))
        for key in ("ot_hours", "ot_amount", "meal_amount")
    } == {
        "ot_hours": (1, 0),
        "ot_amount": (1, 1),
        "meal_amount": (1, 2),
    }
    grid = next(iter(primary_cards.values())).master
    assert all(grid.grid_columnconfigure(index)["weight"] == 1 for index in range(3))
    assert all(
        grid.grid_columnconfigure(index)["uniform"] == "attendance-kpi"
        for index in range(3)
    )
    assert len({type(card) for card in page.kpi_cards.values()}) == 1
    assert all(
        card.cget("background") == ATTENDANCE_OT_CHALK_WHITE
        for card in primary_cards.values()
    )
    assert all(
        card.body.cget("background") == ATTENDANCE_OT_CARD
        for card in primary_cards.values()
    )
    assert all(
        "15" in str(card.value_label.cget("font"))
        for card in page.kpi_cards.values()
    )
    heading_labels = (
        page.attendance_trend_panel.title_label,
        page.trend_panel.title_label,
        page.top_department_panel.title_label,
        page.top_branch_panel.title_label,
    )
    kpi_labels = tuple(card.title_label for card in page.kpi_cards.values())
    value_labels = tuple(card.value_label for card in page.kpi_cards.values())
    assert all(
        page.visual_theme.typography.ui_family in str(label.cget("font"))
        for label in heading_labels
    )
    assert all(
        page.visual_theme.typography.ui_family in str(label.cget("font"))
        for label in (*kpi_labels, *value_labels)
    )
    assert all("bold" in str(label.cget("font")) for label in heading_labels)
    assert all("bold" in str(label.cget("font")) for label in kpi_labels)
    assert all("bold" in str(label.cget("font")) for label in value_labels)
