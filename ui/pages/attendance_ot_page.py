"""Filtered Attendance & OT reports, paged audits and manual maintenance."""

from __future__ import annotations

import calendar
import tkinter as tk
from dataclasses import replace
from datetime import date
from tkinter import ttk

from PIL import Image, ImageTk

from shared.attendance_ot.reporting import (
    AnalyticsFilters,
    DETAIL_COLUMNS,
    DETAIL_LABELS,
    EMPLOYEE_STATUSES,
    MASTER_COLUMNS,
    MONTHS,
    STATUSES,
)
from shared.attendance_ot.models import SourceType
from ui.constants import (
    ATTENDANCE_OT_CARD,
    ATTENDANCE_OT_CHALK_BLUE,
    ATTENDANCE_OT_CHALK_PINK,
    ATTENDANCE_OT_CHALK_YELLOW,
)
from ui.pages.base_page import BasePage
from ui.pages.attendance_ot_widgets import (
    DataTable,
    KPICard,
    LateMatrixTable,
    MultiSelect,
    ScrollBody,
    SimpleTrendPanel,
    TopFiveBarList,
    bind_wheel,
)
from ui.theme.attendance_ot import (
    apply_attendance_ot_styles,
    resolve_attendance_ot_theme,
)
from ui.widgets import DateEntry
from ui.widgets.pagination_bar import PaginationBar


KPI_CARD_SPECS = (
    ("records", "Records", ATTENDANCE_OT_CHALK_BLUE, "records.ico"),
    ("employees", "Employees", ATTENDANCE_OT_CHALK_YELLOW, "employee.ico"),
    ("late_records", "Late Records", ATTENDANCE_OT_CHALK_PINK, "late_records.ico"),
    ("ot_hours", "OT Hours", ATTENDANCE_OT_CHALK_BLUE, "ot_hours.ico"),
    ("ot_amount", "OT Amount", ATTENDANCE_OT_CHALK_YELLOW, "ot_amount.ico"),
    ("meal_amount", "Meal Amount", ATTENDANCE_OT_CHALK_PINK, "meal_amount.ico"),
)


class AttendanceOTPage(BasePage):
    page_id = "attendance_ot"
    title = "ATT & OT"
    subtitle = "Attendance, overtime, dan audit source data."
    icon_name = "info.ico"
    TAB_TITLES = (
        "Dashboard",
        "Data Terlambat",
        "Detail Data",
        "Master Data",
        "Source Files",
        "Data Update",
    )
    page_size = 200
    show_page_heading = False

    def __init__(self, parent, context):
        self._storage_checked = False
        self._busy = False
        self._navigation_locked = False
        self._disposed = False
        self._pending_reload = False
        self._filter_options_cache = None
        self.filters = AnalyticsFilters()
        self.matrix_year = date.today().year
        self.offsets = {name: 0 for name in self.TAB_TITLES}
        self.totals = {name: 0 for name in self.TAB_TITLES}
        self._source_items = ()
        self._data_update_pending = False
        self._actions = []
        super().__init__(parent, context)

    def build_content(self):
        self.services = self.context.app_services
        self.storage_service = self.services.attendance_ot_service
        self.queries = getattr(self.services, "attendance_ot_analytics_service", None)
        self.visual_theme = resolve_attendance_ot_theme(
            self,
            self.context.assets_path,
            logger=self.context.logger,
        )
        self._configure_professional_styles()
        self.configure(style="AttendanceOTPage.TFrame")
        self.rowconfigure(1, weight=0)
        self.rowconfigure(3, weight=1)
        self.progress_var = tk.StringVar(value="Ready. Refresh Data dijalankan manual.")
        self.prompt_frame = ttk.Frame(self, style="AttendanceOTCard.TFrame", padding=10)
        self.prompt_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            self.prompt_frame,
            text="Storage analytics perlu dibuat / dimigrasikan. Create untuk melanjutkan.",
            style="AttendanceOTCardBody.TLabel",
        ).pack(side="left")
        actions = ttk.Frame(self.prompt_frame, style="AttendanceOTCard.TFrame")
        actions.pack(side="right")
        self._button(actions, "Create", self.create_storage).pack(side="left")
        self._button(actions, "Later", self.dismiss_prompt).pack(side="left")
        self.prompt_frame.grid_remove()
        self._build_filters()
        toolbar = ttk.Frame(self, style="AttendanceOTSurface.TFrame")
        toolbar.grid(row=2, column=0, sticky="ew", pady=6)
        self.refresh_button = self._button(toolbar, "Refresh Data", self.refresh_data)
        self.refresh_button.pack(side="left")
        self.export_mode = tk.StringVar(value="Current Filter")
        ttk.Combobox(
            toolbar,
            textvariable=self.export_mode,
            values=("Current Filter", "All Data"),
            state="readonly",
            width=15,
            font=self.visual_theme.body_font,
            style="AttendanceOT.TCombobox",
        ).pack(side="left", padx=(12, 4))
        self._button(toolbar, "Export Excel", self.export_excel).pack(side="left")
        self.duplicate_button = self._button(
            toolbar, "Cek Duplicate Data", self.duplicate_data
        )
        self.duplicate_button.pack(side="left", padx=(8, 8))
        progress_area = ttk.Frame(toolbar, style="AttendanceOTSurface.TFrame")
        progress_area.pack(side="right")
        self.refresh_progress = ttk.Progressbar(
            progress_area,
            mode="determinate",
            maximum=100,
            value=0,
            length=140,
            style="AttendanceOT.Horizontal.TProgressbar",
        )
        self.refresh_progress.pack(side="left")
        self.progress_percent_var = tk.StringVar(value="0%")
        self.progress_percent_label = ttk.Label(
            progress_area,
            textvariable=self.progress_percent_var,
            style="AttendanceOTProgress.TLabel",
            width=5,
            anchor="e",
        )
        self.progress_percent_label.pack(side="left", padx=(6, 0))
        self.notebook = ttk.Notebook(self, style="AttendanceOT.TNotebook")
        self.notebook.grid(row=3, column=0, sticky="nsew")
        self.tabs = {}
        for name in self.TAB_TITLES:
            frame = ttk.Frame(
                self.notebook, style="AttendanceOTSurface.TFrame", padding=8
            )
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            self.notebook.add(frame, text=name)
            self.tabs[name] = frame
        self._build_dashboard()
        self._build_data_update()
        self._build_tables()
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.load_view())
        ttk.Label(
            self,
            textvariable=self.progress_var,
            style="AttendanceOTPageStatus.TLabel",
            wraplength=1000,
        ).grid(row=4, column=0, sticky="ew", pady=(6, 0))

    def _button(self, parent, text, command):
        button = ttk.Button(
            parent, text=text, command=command, style="AttendanceOT.TButton"
        )
        self._actions.append(button)
        return button

    def _build_filters(self):
        panel = ttk.Frame(self, style="AttendanceOTSurface.TFrame", padding=8)
        panel.grid(row=1, column=0, sticky="ew")
        self.filter_vars = {
            key: tk.StringVar()
            for key in (
                "period",
                "date_from",
                "date_to",
                "search",
                "status",
                "employee_status",
            )
        }
        self.filter_vars["employee_status"].set("All")
        labels = (
            "Period (YYYY / YYYY-MM)",
            "Date From (MM/DD/YYYY)",
            "Date To (MM/DD/YYYY)",
            "NIK / Name",
            "Attendance Status",
            "Employee Status",
        )
        self.period_box = None
        self.date_from_entry = None
        self.date_to_entry = None
        for index, (key, label) in enumerate(zip(self.filter_vars, labels)):
            panel.columnconfigure(index, weight=1)
            ttk.Label(panel, text=label, style="AttendanceOTStatus.TLabel").grid(
                row=0, column=index, sticky="w", padx=4
            )
            if key in ("period", "status", "employee_status"):
                choices = (
                    ("All", *EMPLOYEE_STATUSES)
                    if key == "employee_status"
                    else (("", *STATUSES) if key == "status" else ("",))
                )
                widget = ttk.Combobox(
                    panel,
                    textvariable=self.filter_vars[key],
                    values=choices,
                    state=(
                        "readonly"
                        if key in ("status", "employee_status")
                        else "normal"
                    ),
                    width=17,
                    font=self.visual_theme.body_font,
                    style="AttendanceOT.TCombobox",
                )
                if key == "period":
                    self.period_box = widget
            elif key in ("date_from", "date_to"):
                widget = DateEntry(
                    panel,
                    textvariable=self.filter_vars[key],
                    width=14,
                )
                if key == "date_from":
                    self.date_from_entry = widget
                else:
                    self.date_to_entry = widget
                widget.configure(style="AttendanceOTSurface.TFrame")
                widget.entry.configure(style="AttendanceOT.TEntry")
                widget.calendar_button.configure(style="AttendanceOT.TButton")
            else:
                widget = ttk.Entry(
                    panel,
                    textvariable=self.filter_vars[key],
                    width=18,
                    font=self.visual_theme.body_font,
                    style="AttendanceOT.TEntry",
                )
            widget.grid(row=1, column=index, sticky="ew", padx=4)
            entry = widget.entry if isinstance(widget, DateEntry) else widget
            entry.bind("<Return>", lambda e: self.apply_filters())
        self.multis = {
            key: MultiSelect(panel, label, theme=self.visual_theme)
            for key, label in (
                ("branches", "Branch"),
                ("pay_groups", "Pay Group"),
                ("departments", "Department"),
                ("divisions", "Division"),
            )
        }
        for index, widget in enumerate(self.multis.values()):
            widget.grid(row=2, column=index, sticky="ew", padx=4, pady=6)
        actions = ttk.Frame(panel, style="AttendanceOTSurface.TFrame")
        actions.grid(row=2, column=4, columnspan=2, sticky="e")
        self.apply_button = self._button(actions, "Apply", self.apply_filters)
        self.apply_button.configure(style="AttendanceOTApply.TButton")
        self.apply_button.pack(side="left", padx=4)
        self.reset_button = self._button(actions, "Reset", self.reset_filters)
        self.reset_button.configure(style="AttendanceOTReset.TButton")
        self.reset_button.pack(side="left", padx=4)
        self.active_filters = tk.StringVar(value="Active filters: All Data")
        ttk.Label(
            panel,
            textvariable=self.active_filters,
            style="AttendanceOTStatus.TLabel",
            wraplength=1000,
        ).grid(row=3, column=0, columnspan=6, sticky="ew", padx=4)

    def _build_dashboard(self):
        body = ScrollBody(self.tabs["Dashboard"], theme=self.visual_theme)
        body.grid(row=1, column=0, sticky="nsew")
        self.dashboard_scroll = body
        body.content.columnconfigure(0, weight=1)
        self.dashboard_header = tk.Frame(
            body.content,
            background=self.visual_theme.palette.chalk_white,
            highlightbackground=self.visual_theme.palette.ink,
            highlightthickness=1,
            padx=2,
            pady=2,
        )
        self.dashboard_header.grid(
            row=0, column=0, sticky="ew", padx=4, pady=(0, 10)
        )
        header_body = tk.Frame(
            self.dashboard_header,
            background=ATTENDANCE_OT_CARD,
            padx=14,
            pady=10,
        )
        header_body.pack(fill="both", expand=True)
        self.dashboard_header_accent = tk.Frame(
            header_body,
            background=ATTENDANCE_OT_CHALK_YELLOW,
            height=6,
            borderwidth=0,
        )
        self.dashboard_header_accent.pack(fill="x", pady=(0, 10))
        self.dashboard_header_accent.pack_propagate(False)
        self.dashboard_title = tk.Label(
            header_body,
            text="Attendance & Overtime Overview",
            background=ATTENDANCE_OT_CARD,
            foreground=self.visual_theme.palette.ink,
            font=self.visual_theme.display_font,
            anchor="center",
        )
        self.dashboard_title.pack(fill="x")
        cards = ttk.Frame(body.content, style="AttendanceOTSurface.TFrame")
        cards.grid(row=1, column=0, sticky="ew")
        self.kpi_vars = {}
        self.kpi_cards = {}
        self.kpi_card_bodies = {}
        self.kpi_icons = {}
        for column in range(3):
            cards.columnconfigure(column, weight=1, uniform="attendance-kpi")
        for index, (key, label, accent, icon_name) in enumerate(KPI_CARD_SPECS):
            variable = tk.StringVar(value="—")
            self.kpi_vars[key] = variable
            icon = self._load_kpi_icon(icon_name)
            self.kpi_icons[key] = icon
            card = KPICard(
                cards,
                title=label,
                variable=variable,
                accent=accent,
                icon=icon,
                theme=self.visual_theme,
            )
            card.grid(
                row=index // 3,
                column=index % 3,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            self.kpi_cards[key] = card
            self.kpi_card_bodies[key] = card.body

        self.attendance_trend_panel = SimpleTrendPanel(
            body.content,
            MONTHS,
            title="Attendance Record Trend",
            accent=ATTENDANCE_OT_CHALK_BLUE,
            theme=self.visual_theme,
        )
        self.attendance_trend_panel.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=4,
            pady=(8, 4),
        )

        self.trend_panel = SimpleTrendPanel(
            body.content,
            MONTHS,
            title="Late Record Trend",
            accent=ATTENDANCE_OT_CHALK_PINK,
            theme=self.visual_theme,
        )
        self.trend_panel.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        rankings = ttk.Frame(
            body.content,
            style="AttendanceOTSurface.TFrame",
        )
        rankings.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        rankings.columnconfigure((0, 1), weight=1, uniform="rank-card")
        self.top_department_panel = TopFiveBarList(
            rankings,
            title="Top 5 Late HO Departments",
            accent=ATTENDANCE_OT_CHALK_YELLOW,
            theme=self.visual_theme,
        )
        self.top_department_panel.grid(
            row=0, column=0, sticky="nsew", padx=(4, 2), pady=4
        )
        self.top_branch_panel = TopFiveBarList(
            rankings,
            title="Top 5 Late Branches",
            accent=ATTENDANCE_OT_CHALK_BLUE,
            theme=self.visual_theme,
        )
        self.top_branch_panel.grid(
            row=0, column=1, sticky="nsew", padx=(2, 4), pady=4
        )
        body.bind_children()

    def _load_kpi_icon(self, icon_name):
        """Load the transparent ICO directly for an ATT&OT KPI symbol."""

        path = self.context.assets_path / "icons" / icon_name
        if not path.is_file():
            return None
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA").resize(
                    (52, 52), Image.Resampling.LANCZOS
                )
            return ImageTk.PhotoImage(image, master=self)
        except (OSError, RuntimeError, tk.TclError) as exc:
            self.context.logger.warning("KPI icon cannot be loaded: %s (%s)", path, exc)
            return None

    def _pager(self, parent, tab):
        pager = PaginationBar(
            parent, lambda: self.turn_page(tab, -1), lambda: self.turn_page(tab, 1)
        )
        pager.grid(row=2, column=0, sticky="e", pady=6)
        pager.label.configure(style="AttendanceOTStatus.TLabel")
        for button in (pager.previous_button, pager.next_button):
            button.configure(style="AttendanceOT.TButton")
        return pager

    def _build_tables(self):
        self.tables = {}
        self.pagers = {}
        frame = self.tabs["Detail Data"]
        self.tables["Detail Data"] = DataTable(
            frame,
            DETAIL_COLUMNS,
            DETAIL_LABELS,
            theme=self.visual_theme,
            tree_style="AttendanceOTDetail.Treeview",
            frame_style="AttendanceOTDetail.TFrame",
            zebra_stripes=True,
        )
        self.tables["Detail Data"].grid(row=1, column=0, sticky="nsew")
        self.pagers["Detail Data"] = self._pager(frame, "Detail Data")
        frame = self.tabs["Data Terlambat"]
        controls = ttk.Frame(frame, style="AttendanceOTSurface.TFrame")
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.year_var = tk.StringVar(value=str(self.matrix_year))
        self.class_var = tk.StringVar()
        for label, var, values in (
            ("Year", self.year_var, ()),
            ("HO / Branch", self.class_var, ("", "HO", "BRANCH")),
        ):
            ttk.Label(controls, text=label, style="AttendanceOTBody.TLabel").pack(
                side="left", padx=4
            )
            ttk.Combobox(
                controls,
                textvariable=var,
                values=values,
                state="readonly" if values else "normal",
                width=10,
                font=self.visual_theme.body_font,
                style="AttendanceOT.TCombobox",
            ).pack(side="left")
        self._button(controls, "Apply year / class", self.apply_filters).pack(
            side="left", padx=8
        )
        ttk.Label(
            controls,
            text="Double-click employee: Detail Data. Group totals = current page.",
            style="AttendanceOTStatus.TLabel",
        ).pack(side="left")
        self.tables["Data Terlambat"] = LateMatrixTable(
            frame,
            (*MONTHS, "Total"),
            on_employee_open=self.open_matrix_employee,
            theme=self.visual_theme,
        )
        self.tables["Data Terlambat"].grid(row=1, column=0, sticky="nsew")
        self.pagers["Data Terlambat"] = self._pager(frame, "Data Terlambat")
        frame = self.tabs["Master Data"]
        controls = ttk.Frame(frame, style="AttendanceOTSurface.TFrame")
        controls.grid(row=0, column=0, sticky="ew")
        self.master_search = tk.StringVar()
        ttk.Label(
            controls, text="Read-only audit search", style="AttendanceOTBody.TLabel"
        ).pack(side="left", padx=4)
        ttk.Entry(
            controls,
            textvariable=self.master_search,
            font=self.visual_theme.body_font,
            style="AttendanceOT.TEntry",
        ).pack(
            side="left"
        )
        self._button(controls, "Search master", self.search_master).pack(
            side="left", padx=6
        )
        self.master_notebook = ttk.Notebook(frame, style="AttendanceOT.TNotebook")
        self.master_notebook.grid(row=1, column=0, sticky="nsew", pady=6)
        self.master_tables = {}
        for kind, columns in MASTER_COLUMNS.items():
            table = DataTable(
                self.master_notebook,
                columns,
                tuple(c.replace("_", " ").title() for c in columns),
                theme=self.visual_theme,
            )
            self.master_notebook.add(table, text=kind)
            self.master_tables[kind] = table
        self.master_notebook.bind(
            "<<NotebookTabChanged>>", lambda e: self.search_master()
        )
        self.pagers["Master Data"] = self._pager(frame, "Master Data")
        frame = self.tabs["Source Files"]
        self.tables["Source Files"] = DataTable(
            frame,
            ("file", "source_type", "rows", "status", "last_import"),
            ("File", "Source Type", "Rows", "Status", "Last Import"),
            theme=self.visual_theme,
        )
        self.tables["Source Files"].grid(row=1, column=0, sticky="nsew")
        self.source_tree = self.tables["Source Files"].tree
        self.source_tree.bind("<<TreeviewSelect>>", self.source_selected)
        self.pagers["Source Files"] = self._pager(frame, "Source Files")
        self.source_detail = tk.StringVar(
            value="Select a file to see path and error details."
        )
        ttk.Label(
            frame,
            textvariable=self.source_detail,
            style="AttendanceOTBody.TLabel",
            wraplength=900,
        ).grid(row=3, column=0, sticky="ew")

    def _build_data_update(self):
        frame = self.tabs["Data Update"]
        frame.rowconfigure(1, weight=0)
        ttk.Label(
            frame,
            text=(
                "Update memindai folder Settings dan subfoldernya, lalu hanya "
                "memproses file baru atau berubah. Setiap source memakai transaksi "
                "terpisah."
            ),
            style="AttendanceOTBody.TLabel",
            wraplength=1000,
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        panel = ttk.Frame(frame, style="AttendanceOTSurface.TFrame", padding=8)
        panel.grid(row=1, column=0, sticky="ew")
        panel.columnconfigure(1, weight=1)
        self.data_update_vars = {}
        self.data_update_labels = {}
        self.data_update_buttons = {}
        specs = (
            (
                SourceType.EMPLOYEE,
                "Update Employee",
                "AttendanceOTDataUpdateEmployee.TButton",
            ),
            (
                SourceType.SCHEDULE,
                "Update Schedule",
                "AttendanceOTDataUpdateSchedule.TButton",
            ),
            (
                SourceType.ATTENDANCE_OT,
                "Update Attendance & OT",
                "AttendanceOTDataUpdateAttendance.TButton",
            ),
        )
        for row, (source_type, label, button_style) in enumerate(specs):
            button = self._button(
                panel,
                label,
                lambda value=source_type: self.update_data_source(value),
            )
            button.configure(style=button_style, width=24)
            button.grid(row=row, column=0, sticky="ew", padx=(0, 12), pady=5)
            self.data_update_buttons[source_type.value] = button
            variable = tk.StringVar(
                value="Last Update: — | Found: 0 | Processed: 0 | Never"
            )
            self.data_update_vars[source_type.value] = variable
            status_label = ttk.Label(
                panel,
                textvariable=variable,
                style="AttendanceOTDataUpdatePending.TLabel",
                wraplength=850,
            )
            status_label.grid(row=row, column=1, sticky="w", pady=5)
            self.data_update_labels[source_type.value] = status_label
        self.data_update_all_button = self._button(
            panel, "Update All", self.update_all_data
        )
        self.data_update_all_button.configure(
            style="AttendanceOTDataUpdateAll.TButton",
            width=24,
        )
        self.data_update_all_button.grid(
            row=len(specs), column=0, sticky="ew", padx=(0, 12), pady=(12, 5)
        )
        self.data_update_notice = tk.StringVar()
        ttk.Label(
            frame,
            textvariable=self.data_update_notice,
            style="AttendanceOTDataUpdatePending.TLabel",
            font=self.visual_theme.body_bold_font,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _configure_professional_styles(self):
        apply_attendance_ot_styles(self, self.visual_theme)

    def on_show(self):
        if not self._storage_checked:
            self._storage_checked = True
            self.refresh_storage_prompt()
        self.load_view(options=True)

    def refresh_storage_prompt(self):
        status = self.storage_service.resolve_status()
        if status.database_exists and status.database_valid:
            self.prompt_frame.grid_remove()
        else:
            self.prompt_frame.grid()

    def dismiss_prompt(self):
        self.prompt_frame.grid_remove()

    def create_storage(self):
        def done(status):
            self.prompt_frame.grid_remove()
            self.progress_var.set(
                f"Storage siap: {status.database_path}. Jalankan Refresh Data."
            )

        self.run_task(self.storage_service.initialize, done, "Initialize analytics")

    def _tab(self):
        return self.notebook.tab(self.notebook.select(), "text")

    def apply_filters(self):
        try:
            year = int(self.year_var.get())
            if not 1 <= year <= 9999:
                raise ValueError("Year tidak valid.")
            values = {
                key: var.get().strip()
                for key, var in self.filter_vars.items()
                if key not in ("date_from", "date_to")
            }
            values["date_from"] = self.date_from_entry.get_iso() or ""
            values["date_to"] = self.date_to_entry.get_iso() or ""
            if values["employee_status"] == "All":
                values["employee_status"] = ""
            filters = AnalyticsFilters(
                **values,
                **{key: multi.selected for key, multi in self.multis.items()},
                classification=self.class_var.get(),
            )
        except ValueError as exc:
            self.services.dialog_service.warning("Filters", str(exc))
            return
        self.matrix_year = year
        self.filters = filters
        self.active_filters.set(
            "Active filters: " + filters.describe() + f"; Matrix year: {year}"
        )
        for tab in self.offsets:
            self.offsets[tab] = 0
        self.load_view()

    def reset_filters(self):
        for var in self.filter_vars.values():
            var.set("")
        self.filter_vars["employee_status"].set("All")
        self.class_var.set("")
        for multi in self.multis.values():
            multi.set_selected(())
        self.apply_filters()

    def _dashboard_view(self, filters, year):
        """Compose dashboard visuals from existing read-only report methods."""

        with self.queries.snapshot() as session:
            value = session.dashboard(
                filters,
                ranking_keys=("HO Departments", "Branches"),
            )
            trends = session.monthly_trends(filters, year)
        return {
            **value,
            "attendance_trend": trends["attendance"],
            "trend": trends["late"],
        }

    def _filter_options_for_load(self):
        """Reuse immutable filter choices until analytics data changes."""

        if self._filter_options_cache is None:
            self._filter_options_cache = self.queries.filter_options()
        return self._filter_options_cache

    def _invalidate_filter_options(self):
        self._filter_options_cache = None

    def load_view(self, *, options=False, on_success=None):
        if not self.queries or self._disposed:
            return
        if self._busy:
            self._pending_reload = True
            return
        if not self.storage_service.resolve_status().database_valid:
            return
        tab = self._tab()
        filters = self.filters
        offset = self.offsets[tab]
        year = self.matrix_year
        kind = self.master_notebook.tab(self.master_notebook.select(), "text")
        search = self.master_search.get().strip()

        def work():
            if tab == "Dashboard":
                value = self._dashboard_view(filters, year)
            elif tab == "Data Update":
                service = getattr(
                    self.services, "attendance_ot_import_service", None
                )
                value = service.data_update_statuses() if service else ()
            else:
                value = self.queries.view(
                    filters,
                    tab=tab,
                    offset=offset,
                    year=year,
                    master_kind=kind,
                    master_search=search,
                )
            return value, self._filter_options_for_load() if options else None

        def done(result):
            value, choices = result
            if choices:
                self.period_box.configure(values=("", *choices["periods"]))
                for key, multi in self.multis.items():
                    multi.set_values(choices[key])
            self._render(tab, value, kind)
            if on_success is not None:
                on_success()

        # Initial and filtered report reads run in the background. They must not
        # trap the user on this page while a large analytics database is read.
        self.run_task(work, done, "Loading " + tab, lock_navigation=False)

    def _render(self, tab, value, kind):
        if tab == "Dashboard":
            for key, var in self.kpi_vars.items():
                number = value["kpi"][key]
                if key in ("ot_amount", "meal_amount"):
                    var.set(f"Rp. {number:,.2f}")
                elif key == "ot_hours":
                    var.set(f"{number:,.2f}")
                else:
                    var.set(f"{number:,}")
            self.attendance_trend_panel.set_values(
                value.get("attendance_trend", (0,) * len(MONTHS))
            )
            self.trend_panel.set_values(value.get("trend", (0,) * len(MONTHS)))

            departments = tuple(
                (
                    row.get("department") or "—",
                    int(row.get("late_count") or 0),
                )
                for row in value["rankings"].get("HO Departments", ())[:5]
            )
            branches = tuple(
                (row.get("branch") or "—", int(row.get("late_count") or 0))
                for row in value["rankings"].get("Branches", ())[:5]
            )
            self.top_department_panel.set_items(departments)
            self.top_branch_panel.set_items(branches)
            return
        if tab == "Data Update":
            self._render_data_update_statuses(value)
            return
        self.totals[tab] = value.total
        self.pagers[tab].update_state(
            offset=value.offset, limit=value.limit, total=value.total
        )
        if tab == "Detail Data":
            self.tables[tab].rows(value.items, DETAIL_COLUMNS)
        elif tab == "Master Data":
            self.master_tables[kind].rows(value.items, MASTER_COLUMNS[kind])
        elif tab == "Source Files":
            self._source_items = value.items
            rows = tuple(
                {
                    "file": r["filename"],
                    "source_type": r["source_type"],
                    "rows": r["row_count"],
                    "status": r["status"],
                    "last_import": r["imported_at"],
                }
                for r in value.items
            )
            self.tables[tab].rows(
                rows, ("file", "source_type", "rows", "status", "last_import")
            )
        elif tab == "Data Terlambat":
            self.tables[tab].set_rows(value.items)

    def turn_page(self, tab, direction):
        if self._busy:
            return
        offset = max(0, self.offsets[tab] + direction * self.page_size)
        if direction > 0 and offset >= self.totals[tab]:
            return
        self.offsets[tab] = offset
        self.load_view()

    def search_master(self):
        self.offsets["Master Data"] = 0
        if hasattr(self, "notebook") and self._tab() == "Master Data":
            self.load_view()

    def source_selected(self, _event=None):
        selected = self.source_tree.selection()
        if selected and int(selected[0]) < len(self._source_items):
            row = self._source_items[int(selected[0])]
            self.source_detail.set(
                f"Path: {row['source_path']}\nError: {row['error_detail'] or '-'}"
            )

    def open_matrix_employee(self, emplid):
        if emplid:
            self.filters = replace(
                self.filters,
                emplid=emplid,
                status="LATE",
                date_from=max(self.filters.date_from, f"{self.matrix_year}-01-01"),
                date_to=min(
                    self.filters.date_to or f"{self.matrix_year}-12-31",
                    f"{self.matrix_year}-12-31",
                ),
            )
            self.active_filters.set("Active filters: " + self.filters.describe())
            self.offsets["Detail Data"] = 0
            self.notebook.select(self.tabs["Detail Data"])

    def _legacy_source_refresh(self):
        self.refresh_data()

    def _render_data_update_statuses(self, results):
        for result in results:
            last_update = result.last_update or "—"
            detail = f" | Error: {result.error_detail}" if result.error_detail else ""
            variable = self.data_update_vars.get(result.source_type)
            if variable is not None:
                variable.set(
                    f"Last Update: {last_update} | Found: {result.files_found} | "
                    f"New: {result.files_new} | Changed: {result.files_changed} | "
                    f"Skipped: {result.files_skipped} | "
                    f"Processed: {result.files_processed} | "
                    f"Rows I/U/S: {result.rows_inserted:,}/"
                    f"{result.rows_updated:,}/{result.rows_unchanged:,} | "
                    f"{result.duration_seconds:.2f}s | {result.status.title()}"
                    f"{detail}"
                )
            label = self.data_update_labels.get(result.source_type)
            if label is not None:
                if result.status == "SUCCESS":
                    style_name = "AttendanceOTDataUpdateComplete.TLabel"
                elif result.status == "ERROR":
                    style_name = "AttendanceOTDataUpdateError.TLabel"
                else:
                    style_name = "AttendanceOTDataUpdatePending.TLabel"
                label.configure(style=style_name)

    def update_data_source(self, source_type):
        service = getattr(self.services, "attendance_ot_import_service", None)
        if service is None:
            return
        self.run_task(
            lambda report: service.update_source(source_type, report),
            lambda result: self._data_update_completed((result,)),
            f"Updating {source_type.value}",
            reporting=True,
            cancellable=False,
        )

    def update_all_data(self):
        service = getattr(self.services, "attendance_ot_import_service", None)
        if service is None:
            return
        self.run_task(
            service.update_all,
            self._data_update_completed,
            "Updating all Attendance & OT sources",
            reporting=True,
            cancellable=False,
        )

    def _data_update_completed(self, results):
        results = tuple(results)
        self._render_data_update_statuses(results)
        success = tuple(result for result in results if result.status == "SUCCESS")
        errors = tuple(result for result in results if result.status == "ERROR")
        if success:
            self._data_update_pending = True
            self.data_update_notice.set("Data updated — Refresh to view latest data")
        lines = [
            f"{result.source_type}: {result.status.title()} | "
            f"Found {result.files_found} | New {result.files_new} | "
            f"Changed {result.files_changed} | Skipped {result.files_skipped} | "
            f"Processed {result.files_processed} | Rows I/U/S "
            f"{result.rows_inserted:,}/{result.rows_updated:,}/"
            f"{result.rows_unchanged:,} | {result.duration_seconds:.2f}s"
            + (f" | {result.error_detail}" if result.error_detail else "")
            for result in results
        ]
        if errors:
            self.services.dialog_service.warning("Data Update", "\n".join(lines))
        else:
            self.services.dialog_service.info("Data Update", "\n".join(lines))

    def refresh_data(self):
        """Reload database-backed views only; never scan configured sources."""

        self._invalidate_filter_options()

        def refreshed():
            self._data_update_pending = False
            self.data_update_notice.set("")
            self.progress_var.set("Refresh completed from attendance_ot.db.")

        self.load_view(options=True, on_success=refreshed)

    def export_excel(self):
        service = getattr(self.services, "attendance_ot_export_service", None)
        if service is None or self._busy:
            return
        filters = (
            self.filters
            if self.export_mode.get() == "Current Filter"
            else AnalyticsFilters()
        )
        path = self.services.dialog_service.save_file(
            title="Export Attendance & OT",
            default_name="Attendance_OT.xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if path:
            self.run_task(
                lambda report: service.export(path, filters, report),
                lambda value: self.services.dialog_service.info(
                    "Export Excel", f"Export selesai:\n{value}"
                ),
                "Export Excel",
                reporting=True,
            )

    def maintenance(self):
        service = getattr(self.services, "attendance_ot_maintenance_service", None)
        if service is None or self._busy:
            return

        def show(info):
            window = tk.Toplevel(self)
            window.title("ATTENDANCE & OT — Database Maintenance")
            window.geometry("780x440")
            window.transient(self.winfo_toplevel())
            window.configure(background=self.visual_theme.palette.surface)
            window.columnconfigure(0, weight=1)
            window.rowconfigure(0, weight=1)
            text = tk.Text(
                window,
                wrap="word",
                font=(self.visual_theme.typography.ui_family, 10),
                background=ATTENDANCE_OT_CARD,
                foreground=self.visual_theme.palette.ink,
                padx=12,
                pady=12,
            )
            text.grid(row=0, column=0, sticky="nsew")
            bar = ttk.Scrollbar(window, orient="vertical", command=text.yview)
            bar.grid(row=0, column=1, sticky="ns")
            text.configure(yscrollcommand=bar.set)
            bind_wheel(text, text)
            text.insert(
                "1.0",
                "\n".join(
                    f"{k.replace('_', ' ').title()}: {v if v is not None else '-'}"
                    for k, v in info.items()
                )
                + "\n\nPurge removes attendance in the selected period. Employee/schedule history is retained. Changed source files can reimport purged rows. Reset clears all analytics data and registry. Source folders/config stay saved. A verified backup is retained beside attendance_ot.db.",
            )
            text.configure(state="disabled")
            actions = ttk.Frame(window, style="AttendanceOTSurface.TFrame")
            actions.grid(row=1, column=0, pady=10)
            for label, command in (
                ("Purge period/year", lambda: self.preview_cleanup("PURGE")),
                ("Reset Analytics Database", lambda: self.preview_cleanup("RESET")),
                ("Compact / VACUUM", self.compact),
                (
                    "Schema Info / Refresh",
                    lambda: (window.destroy(), self.maintenance()),
                ),
            ):
                self._button(actions, label, command).pack(side="left", padx=4)

        self.run_task(service.info, show, "Schema Info")

    def duplicate_data(self):
        service = getattr(self.services, "attendance_ot_maintenance_service", None)
        if service is None or self._busy:
            return

        def show(preview):
            window = tk.Toplevel(self)
            window.title("ATTENDANCE & OT — Duplicate Data")
            window.geometry("980x520")
            window.transient(self.winfo_toplevel())
            window.configure(background=self.visual_theme.palette.surface)
            window.columnconfigure(0, weight=1)
            window.rowconfigure(1, weight=1)

            summary = (
                f"Duplicate groups: {preview.duplicate_groups:,}   |   "
                f"Rows to delete: {preview.duplicate_rows:,}\n"
                "Key: NIK + Date In + Actual In + Date Out + Actual Out. "
                "The earliest imported row is retained."
            )
            ttk.Label(
                window,
                text=summary,
                style="AttendanceOTBody.TLabel",
                wraplength=940,
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)

            columns = (
                "emplid",
                "date_in",
                "time_in",
                "date_out",
                "time_out",
                "source_file",
                "source_sheet",
                "source_row",
            )
            labels = (
                "NIK",
                "Date In",
                "Actual In",
                "Date Out",
                "Actual Out",
                "Duplicate Source",
                "Sheet",
                "Row",
            )
            table = DataTable(
                window,
                columns,
                labels,
                theme=self.visual_theme,
            )
            table.grid(row=1, column=0, sticky="nsew", padx=12)
            table.rows(preview.samples, columns)

            actions = ttk.Frame(window, style="AttendanceOTSurface.TFrame")
            actions.grid(row=2, column=0, pady=12)
            ttk.Button(
                actions,
                text="Check Again",
                command=lambda: (window.destroy(), self.duplicate_data()),
                style="AttendanceOT.TButton",
            ).pack(side="left", padx=4)
            delete_button = ttk.Button(
                actions,
                text="Delete Duplicates",
                command=lambda: self.delete_duplicates(window, preview),
                style="AttendanceOT.TButton",
            )
            delete_button.pack(side="left", padx=4)
            if preview.duplicate_rows == 0:
                delete_button.configure(state="disabled")
            ttk.Button(
                actions,
                text="Close",
                command=window.destroy,
                style="AttendanceOT.TButton",
            ).pack(side="left", padx=4)

        self.run_task(service.preview_duplicates, show, "Checking duplicate data")

    def delete_duplicates(self, window, preview):
        if self._busy or preview.duplicate_rows == 0:
            return
        service = self.services.attendance_ot_maintenance_service
        if not self.services.dialog_service.typed_confirm(
            "Delete Duplicates",
            (
                f"{preview.duplicate_rows:,} duplicate rows in "
                f"{preview.duplicate_groups:,} groups will be deleted.\n\n"
                "One canonical row per key is retained and a verified backup "
                "is created first. Type DELETE DUPLICATES to continue."
            ),
            "DELETE DUPLICATES",
        ):
            return
        window.destroy()

        def done(result):
            self.services.dialog_service.info(
                "Duplicate Data",
                (
                    f"Deleted {result['deleted_records']:,} duplicate rows.\n"
                    f"Backup: {result['backup']}"
                ),
            )
            self.offsets = {tab: 0 for tab in self.TAB_TITLES}
            self._invalidate_filter_options()
            self.load_view(options=True)

        self.run_task(
            lambda: service.delete_duplicates(
                preview, confirmation="DELETE DUPLICATES"
            ),
            done,
            "Deleting duplicate data",
            cancellable=False,
        )

    def preview_cleanup(self, operation):
        if self._busy:
            return
        service = self.services.attendance_ot_maintenance_service
        low = high = ""
        if operation == "PURGE":
            value = self.services.dialog_service.prompt_text(
                "Purge period/year", "Hapus attendance untuk periode YYYY atau YYYY-MM:"
            )
            if value is None:
                return
            try:
                value = value.strip()
                AnalyticsFilters(period=value)
                if not value:
                    raise ValueError("Period wajib diisi.")
                year = int(value[:4])
                if len(value) == 4:
                    low, high = f"{year:04d}-01-01", f"{year:04d}-12-31"
                else:
                    month = int(value[5:7])
                    low, high = (
                        value + "-01",
                        value + f"-{calendar.monthrange(year, month)[1]:02d}",
                    )
            except ValueError as exc:
                self.services.dialog_service.warning("Purge", str(exc))
                return

        def confirm(preview):
            if self.services.dialog_service.typed_confirm(
                operation,
                preview.describe()
                + f"\n\nBackup dibuat dahulu. Ketik {operation} untuk menghapus data tersebut.",
                operation,
            ):
                self.run_task(
                    lambda: service.execute(preview, confirmation=operation),
                    self._cleanup_done,
                    operation,
                    cancellable=False,
                )

        self.run_task(
            lambda: service.preview(operation, low, high),
            confirm,
            "Preparing deletion summary",
        )

    def _cleanup_done(self, value):
        self.services.dialog_service.info(
            "Maintenance",
            f"Deleted {value['deleted_records']:,} attendance records.\nBackup: {value['backup']}",
        )
        self.offsets = {tab: 0 for tab in self.TAB_TITLES}
        self._invalidate_filter_options()
        self.load_view(options=True)

    def compact(self):
        self.run_task(
            self.services.attendance_ot_maintenance_service.vacuum,
            lambda value: self.services.dialog_service.info(
                "VACUUM", f"Compact selesai. Size: {value['size_bytes']:,} bytes"
            ),
            "Compacting analytics",
            cancellable=False,
        )

    def run_task(
        self,
        function,
        on_success,
        message,
        *,
        reporting=False,
        cancellable=True,
        lock_navigation=True,
    ):
        if self._busy or self._disposed:
            return
        self._busy = True
        self._navigation_locked = lock_navigation
        self.progress_var.set(message)
        self._set_refresh_progress(None)
        for button in self._actions:
            if button.winfo_exists():
                button.configure(state="disabled")

        def progress(event):
            if not self._disposed:
                if hasattr(event, "files_processed"):
                    self.progress_var.set(
                        f"{event.message} | Processed {event.files_processed} | Skipped {event.files_skipped} | Error {event.files_error} | Rows {event.rows_imported:,}"
                    )
                else:
                    self.progress_var.set(str(event))
                percent = getattr(event, "percent", None)
                if percent is None and isinstance(event, str):
                    percent = self._export_progress_percent(event)
                self._set_refresh_progress(percent)

        def done(result):
            if self._disposed:
                return
            self._busy = False
            self._navigation_locked = False
            self._actions = [
                button for button in self._actions if button.winfo_exists()
            ]
            for button in self._actions:
                button.configure(state="normal")
            if result.success:
                business_error = self._result_contains_errors(result.value)
                self._set_refresh_progress(
                    100,
                    state="error" if business_error else "success",
                )
                self.progress_var.set(message + " completed")
                on_success(result.value)
            else:
                self._set_refresh_progress(100, state="error")
                self.progress_var.set(result.error or "Operation failed")
                self.services.dialog_service.error(
                    message, result.error or "Operation failed"
                )
            if self._pending_reload and not self._busy:
                self._pending_reload = False
                self.load_view()

        runner = self.services.task_runner
        if reporting:
            runner.submit_reporting(
                function, on_done=done, on_progress=progress, cancellable=cancellable
            )
        else:
            runner.submit(function, on_done=done, cancellable=cancellable)

    def _set_refresh_progress(
        self,
        percent: int | None,
        *,
        state: str = "running",
    ) -> None:
        self.refresh_progress.stop()
        styles = {
            "running": "AttendanceOT.Horizontal.TProgressbar",
            "success": "AttendanceOTSuccess.Horizontal.TProgressbar",
            "error": "AttendanceOTError.Horizontal.TProgressbar",
        }
        if percent is None:
            self.refresh_progress.configure(
                mode="indeterminate",
                value=0,
                style=styles[state],
            )
            self.progress_percent_var.set("…")
            self.refresh_progress.start(12)
            return
        value = max(0, min(100, int(percent)))
        self.refresh_progress.configure(
            mode="determinate",
            value=value,
            style=styles[state],
        )
        self.progress_percent_var.set(f"{value}%")

    @staticmethod
    def _export_progress_percent(message: str) -> int | None:
        stages = (
            ("Export Overview", 10),
            ("Export Late_Summary", 25),
            ("Export Detail_Data", 45),
            ("Export Employee_Summary", 70),
            ("Export Source_Files", 85),
            ("Export completed", 100),
        )
        return next(
            (percent for prefix, percent in stages if message.startswith(prefix)),
            None,
        )

    @staticmethod
    def _result_contains_errors(value) -> bool:
        values = value if isinstance(value, (tuple, list)) else (value,)
        return any(getattr(item, "status", None) == "ERROR" for item in values)

    def can_navigate_away(self):
        return not self._navigation_locked

    def dispose(self):
        self._disposed = True
