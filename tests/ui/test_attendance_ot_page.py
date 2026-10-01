"""Tk shell contracts for the Sprint 1 Attendance & OT page."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from shared.attendance_ot.reporting import MONTHS
from ui.context import AppContext
from ui.pages.attendance_ot_page import AttendanceOTPage
from ui.pages.attendance_ot_widgets import LATE_CELL_BLUE, LATE_CELL_ORANGE


class _Analytics:
    def resolve_status(self):
        return SimpleNamespace(database_exists=False, database_valid=False)


def test_attendance_ot_page_has_five_tabs_and_create_later_prompt(
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
    prompt_buttons = {
        child.cget("text")
        for container in page.prompt_frame.winfo_children()
        for child in container.winfo_children()
        if child.winfo_class() == "TButton"
    }
    assert prompt_buttons == {"Create", "Later"}
    assert page.prompt_frame.grid_info()


def test_attendance_ot_content_uses_professional_windows_font(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-font-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)
    assert "Segoe UI" in str(page.tk.call("ttk::style", "configure", "AttendanceOTBody.TLabel", "-font"))


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
    assert page.maintenance_button.cget("text") == "Database Maintenance"
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

    assert table.header_colors == {
        "actual_time_in": "#2563EB",
        "actual_time_out": "#2563EB",
        "late_status": "#EA7600",
    }
    assert set(table.heading_images) == {
        "actual_time_in",
        "actual_time_out",
        "late_status",
    }


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

    assert page.multis["divisions"].title == "Division"

    page.apply_filters()

    assert page.filter_vars["date_from"].get() == "09/01/2026"
    assert page.filter_vars["date_to"].get() == "09/30/2026"
    assert page.filters.date_from == "2026-09-01"
    assert page.filters.date_to == "2026-09-30"
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
    assert matrix.canvas.itemcget(matrix.cell_items[jan_key], "fill") == LATE_CELL_BLUE
    assert (
        matrix.canvas.itemcget(matrix.cell_items[feb_key], "fill")
        == LATE_CELL_ORANGE
    )
    assert matrix.canvas.itemcget(matrix.cell_text_items[jan_key], "text") == "8"
    assert matrix.canvas.itemcget(matrix.cell_text_items[feb_key], "text") == "12"
    assert mar_key not in matrix.cell_text_items
    assert matrix.canvas.itemcget(matrix.cell_items[mar_key], "fill") == "#F7F1DD"
    assert (
        matrix.canvas.itemcget(matrix.cell_items[group_mar_key], "fill")
        == "#F7F1DD"
    )


def test_dashboard_top_late_rankings_are_colored_cards(tk_root, tmp_path) -> None:
    services = SimpleNamespace(attendance_ot_service=_Analytics())
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-ranking-cards-test"),
        app_services=services,
    )
    page = AttendanceOTPage(tk_root, context)

    assert tuple(page.rank_cards) == (
        "HO Employees",
        "BRANCH Employees",
        "Branches",
        "HO Departments",
    )
    assert {card.cget("style") for card in page.rank_cards.values()} == {
        "AttendanceOTRankBlue.TFrame",
        "AttendanceOTRankOrange.TFrame",
        "AttendanceOTRankGreen.TFrame",
        "AttendanceOTRankGold.TFrame",
    }
    assert {
        (int(card.grid_info()["row"]), int(card.grid_info()["column"]))
        for card in page.rank_cards.values()
    } == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert all(
        card.winfo_children()[0].cget("text").startswith("Top 5 Late")
        for card in page.rank_cards.values()
    )

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
        },
        "Employee",
    )

    assert page.rank_vars["HO Employees"].get() == "1. Alice — 5 LATE RECORDS"
    assert page.rank_vars["BRANCH Employees"].get() == "1. Bob — 4 LATE RECORDS"
    assert page.rank_vars["Branches"].get() == "1. MALILI — 5 LATE RECORDS"
    assert page.rank_vars["HO Departments"].get() == (
        "1. Finance — 3 LATE RECORDS"
    )
    assert page.kpi_vars["ot_amount"].get() == "Rp. 100.00"
    assert page.kpi_vars["meal_amount"].get() == "Rp. 20.00"

    emphasized_names = {
        "HO Employees": "Alice",
        "BRANCH Employees": "Bob",
        "Branches": "MALILI",
        "HO Departments": "Finance",
    }
    for title, expected_name in emphasized_names.items():
        labels = page.rank_lists[title].winfo_children()[0].winfo_children()
        assert labels[1].cget("text") == expected_name
        assert "11" in str(labels[1].cget("font"))
        assert "bold" in str(labels[1].cget("font"))


def test_dashboard_kpis_have_distinct_fills_and_colored_borders(
    tk_root, tmp_path
) -> None:
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
    borders = {card.cget("background") for card in page.kpi_cards.values()}
    fills = {
        body.cget("background") for body in page.kpi_card_bodies.values()
    }
    assert borders == {
        "#4D72B8",
        "#2F8F83",
        "#EA7600",
        "#8064A2",
        "#5E9C3A",
        "#D2A15A",
    }
    assert fills == {
        "#DCEBFF",
        "#D8F0ED",
        "#FFE4C4",
        "#E9E0F7",
        "#DDF3D2",
        "#F8E8BD",
    }
    assert all(
        page.kpi_cards[key].cget("background")
        != page.kpi_card_bodies[key].cget("background")
        for key in page.kpi_cards
    )
