"""Filtered Attendance & OT reports, paged audits and manual maintenance."""

from __future__ import annotations

import calendar
import tkinter as tk
from dataclasses import replace
from datetime import date
from tkinter import ttk

from shared.attendance_ot.reporting import (
    AnalyticsFilters,
    DETAIL_COLUMNS,
    DETAIL_LABELS,
    MASTER_COLUMNS,
    MONTHS,
    STATUSES,
)
from ui.constants import CARD_BACKGROUND, MAIN_HEADER, TEXT_PRIMARY, TEXT_SECONDARY
from ui.pages.base_page import BasePage
from ui.pages.attendance_ot_widgets import (
    DataTable,
    LateMatrixTable,
    MultiSelect,
    ScrollBody,
    bind_wheel,
)
from ui.widgets import DateEntry
from ui.widgets.pagination_bar import PaginationBar


DETAIL_HEADER_COLORS = {
    "actual_time_in": "#2563EB",
    "actual_time_out": "#2563EB",
    "late_status": "#EA7600",
}

RANK_CARD_STYLES = (
    ("Blue", "#DCEBFF", "#234E8A"),
    ("Orange", "#FFE4C4", "#9A4D00"),
    ("Green", "#DDF3D2", "#356B20"),
    ("Gold", "#F8E8BD", "#76520B"),
)

KPI_CARD_STYLES = (
    ("Blue", "#DCEBFF", "#4D72B8", "#234E8A"),
    ("Teal", "#D8F0ED", "#2F8F83", "#246D65"),
    ("Orange", "#FFE4C4", "#EA7600", "#934A00"),
    ("Purple", "#E9E0F7", "#8064A2", "#594472"),
    ("Green", "#DDF3D2", "#5E9C3A", "#356B20"),
    ("Gold", "#F8E8BD", "#D2A15A", "#76520B"),
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
    )
    page_size = 200
    show_page_heading = False

    def __init__(self, parent, context):
        self._storage_checked = False
        self._busy = False
        self._navigation_locked = False
        self._disposed = False
        self._pending_reload = False
        self.filters = AnalyticsFilters()
        self.matrix_year = date.today().year
        self.offsets = {name: 0 for name in self.TAB_TITLES}
        self.totals = {name: 0 for name in self.TAB_TITLES}
        self._source_items = ()
        self._actions = []
        super().__init__(parent, context)

    def build_content(self):
        self.services = self.context.app_services
        self.storage_service = self.services.attendance_ot_service
        self.queries = getattr(self.services, "attendance_ot_analytics_service", None)
        self._configure_professional_styles()
        self.rowconfigure(1, weight=0)
        self.rowconfigure(3, weight=1)
        self.progress_var = tk.StringVar(value="Ready. Refresh Data dijalankan manual.")
        self.prompt_frame = ttk.Frame(self, style="AttendanceOTCard.TFrame", padding=10)
        self.prompt_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            self.prompt_frame,
            text="Storage analytics perlu dibuat / dimigrasikan. Create untuk melanjutkan.",
            style="AttendanceOTBody.TLabel",
        ).pack(side="left")
        actions = ttk.Frame(self.prompt_frame)
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
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(12, 4))
        self._button(toolbar, "Export Excel", self.export_excel).pack(side="left")
        self.maintenance_button = self._button(
            toolbar, "Database Maintenance", self.maintenance
        )
        self.maintenance_button.pack(side="left", padx=(8, 4))
        self.duplicate_button = self._button(
            toolbar, "Cek Duplicate Data", self.duplicate_data
        )
        self.duplicate_button.pack(side="left", padx=(4, 8))
        self.refresh_progress = ttk.Progressbar(
            toolbar, mode="indeterminate", length=110
        )
        self.refresh_progress.pack(side="right")
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
        self._build_tables()
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.load_view())
        ttk.Label(
            self,
            textvariable=self.progress_var,
            style="AttendanceOTStatus.TLabel",
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
            for key in ("period", "date_from", "date_to", "search", "status")
        }
        labels = (
            "Period (YYYY / YYYY-MM)",
            "Date From (MM/DD/YYYY)",
            "Date To (MM/DD/YYYY)",
            "NIK / Name",
            "Attendance Status",
        )
        self.period_box = None
        self.date_from_entry = None
        self.date_to_entry = None
        for index, (key, label) in enumerate(zip(self.filter_vars, labels)):
            panel.columnconfigure(index, weight=1)
            ttk.Label(panel, text=label, style="AttendanceOTStatus.TLabel").grid(
                row=0, column=index, sticky="w", padx=4
            )
            if key in ("period", "status"):
                widget = ttk.Combobox(
                    panel,
                    textvariable=self.filter_vars[key],
                    values=("", *STATUSES) if key == "status" else ("",),
                    state="readonly" if key == "status" else "normal",
                    width=17,
                    font=("Segoe UI", 9),
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
            else:
                widget = ttk.Entry(
                    panel,
                    textvariable=self.filter_vars[key],
                    width=18,
                    font=("Segoe UI", 9),
                )
            widget.grid(row=1, column=index, sticky="ew", padx=4)
            entry = widget.entry if isinstance(widget, DateEntry) else widget
            entry.bind("<Return>", lambda e: self.apply_filters())
        self.multis = {
            key: MultiSelect(panel, label)
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
        actions.grid(row=2, column=4, sticky="e")
        self._button(actions, "Apply", self.apply_filters).pack(side="left", padx=4)
        self._button(actions, "Reset", self.reset_filters).pack(side="left", padx=4)
        self.active_filters = tk.StringVar(value="Active filters: All Data")
        ttk.Label(
            panel,
            textvariable=self.active_filters,
            style="AttendanceOTStatus.TLabel",
            wraplength=1000,
        ).grid(row=3, column=0, columnspan=5, sticky="ew", padx=4)

    def _build_dashboard(self):
        body = ScrollBody(self.tabs["Dashboard"])
        body.grid(row=1, column=0, sticky="nsew")
        self.dashboard_scroll = body
        body.content.columnconfigure(0, weight=1)
        cards = ttk.Frame(body.content, style="AttendanceOTSurface.TFrame")
        cards.grid(row=0, column=0, sticky="ew")
        self.kpi_vars = {}
        self.kpi_cards = {}
        self.kpi_card_bodies = {}
        for index, ((key, label), style_info) in enumerate(
            zip(
                (
                    ("records", "Records"),
                    ("employees", "Employees"),
                    ("late_records", "Late Records"),
                    ("ot_hours", "OT Hours"),
                    ("ot_amount", "OT Amount"),
                    ("meal_amount", "Meal Amount"),
                ),
                KPI_CARD_STYLES,
            )
        ):
            cards.columnconfigure(index % 3, weight=1)
            _name, background, border, foreground = style_info
            card = tk.Frame(
                cards,
                background=border,
                borderwidth=0,
                padx=2,
                pady=2,
            )
            card.grid(
                row=index // 3,
                column=index % 3,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            body_frame = tk.Frame(
                card,
                background=background,
                padx=12,
                pady=10,
            )
            body_frame.pack(fill="both", expand=True)
            self.kpi_cards[key] = card
            self.kpi_card_bodies[key] = body_frame
            tk.Label(
                body_frame,
                text=label,
                background=background,
                foreground=foreground,
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w")
            variable = tk.StringVar(value="—")
            self.kpi_vars[key] = variable
            tk.Label(
                body_frame,
                textvariable=variable,
                background=background,
                foreground=foreground,
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", pady=(4, 0))
        self.rank_vars = {}
        self.rank_cards = {}
        self.rank_lists = {}
        rankings = ttk.Frame(
            body.content,
            style="AttendanceOTSurface.TFrame",
        )
        rankings.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        rankings.columnconfigure((0, 1), weight=1, uniform="rank-card")
        for index, (title, style_info) in enumerate(
            zip(
                (
                    "HO Employees",
                    "BRANCH Employees",
                    "Branches",
                    "HO Departments",
                ),
                RANK_CARD_STYLES,
            )
        ):
            style_name = style_info[0]
            frame = ttk.Frame(
                rankings,
                style=f"AttendanceOTRank{style_name}.TFrame",
                padding=14,
                relief="solid",
                borderwidth=1,
            )
            frame.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            self.rank_cards[title] = frame
            ttk.Label(
                frame,
                text="Top 5 Late " + title,
                style=f"AttendanceOTRank{style_name}Title.TLabel",
            ).pack(anchor="w")
            variable = tk.StringVar(value="Belum ada hasil.")
            self.rank_vars[title] = variable
            listing = tk.Frame(
                frame,
                background=style_info[1],
            )
            listing.pack(fill="x", anchor="w", pady=4)
            self.rank_lists[title] = listing
            tk.Label(
                listing,
                text="Belum ada hasil.",
                background=style_info[1],
                foreground=TEXT_PRIMARY,
                font=("Segoe UI", 9),
            ).pack(anchor="w")
        body.bind_children()

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
            header_colors=DETAIL_HEADER_COLORS,
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
                font=("Segoe UI", 9),
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
        ttk.Entry(controls, textvariable=self.master_search, font=("Segoe UI", 9)).pack(
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

    def _configure_professional_styles(self):
        style = ttk.Style(self)
        for suffix in ("Surface.TFrame", "Card.TFrame"):
            style.configure("AttendanceOT" + suffix, background=CARD_BACKGROUND)
        style.configure("AttendanceOT.TNotebook", background=CARD_BACKGROUND)
        style.configure(
            "AttendanceOT.TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=(12, 7)
        )
        for name, size, weight, color in (
            ("Title", 14, "bold", MAIN_HEADER),
            ("Body", 10, "normal", TEXT_SECONDARY),
            ("Status", 9, "normal", TEXT_PRIMARY),
        ):
            style.configure(
                f"AttendanceOT{name}.TLabel",
                background=CARD_BACKGROUND,
                foreground=color,
                font=("Segoe UI", size, weight),
            )
        style.configure("AttendanceOT.TButton", font=("Segoe UI", 9))
        style.configure("AttendanceOT.Treeview", font=("Segoe UI", 9), rowheight=25)
        style.configure("AttendanceOT.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        for name, background, foreground in RANK_CARD_STYLES:
            style.configure(
                f"AttendanceOTRank{name}.TFrame",
                background=background,
            )
            style.configure(
                f"AttendanceOTRank{name}Title.TLabel",
                background=background,
                foreground=foreground,
                font=("Segoe UI", 11, "bold"),
            )
            style.configure(
                f"AttendanceOTRank{name}Body.TLabel",
                background=background,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI", 9),
            )

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
        self.class_var.set("")
        for multi in self.multis.values():
            multi.set_selected(())
        self.apply_filters()

    def load_view(self, *, options=False):
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
            return self.queries.view(
                filters,
                tab=tab,
                offset=offset,
                year=year,
                master_kind=kind,
                master_search=search,
            ), self.queries.filter_options() if options else None

        def done(result):
            value, choices = result
            if choices:
                self.period_box.configure(values=("", *choices["periods"]))
                for key, multi in self.multis.items():
                    multi.set_values(choices[key])
            self._render(tab, value, kind)

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
            for title, rows in value["rankings"].items():
                lines = tuple(
                    (
                        r.get("employee_name")
                        or r.get("branch")
                        or r.get("department")
                        or r.get("emplid"),
                        r["late_count"],
                    )
                    for r in rows
                )
                self.rank_vars[title].set(
                    "\n".join(
                        f"{index}. {name} — {count:,} LATE RECORDS"
                        for index, (name, count) in enumerate(lines, 1)
                    )
                    or "No late records for these filters."
                )
                self._render_ranking_list(title, lines)
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

    def _render_ranking_list(self, title, lines):
        listing = self.rank_lists[title]
        for child in listing.winfo_children():
            child.destroy()
        background = listing.cget("background")
        if not lines:
            tk.Label(
                listing,
                text="No late records for these filters.",
                background=background,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI", 9),
            ).pack(anchor="w")
            return
        emphasize_name = title in {
            "HO Employees",
            "BRANCH Employees",
            "Branches",
            "HO Departments",
        }
        for index, (name, count) in enumerate(lines, 1):
            row = tk.Frame(listing, background=background)
            row.pack(fill="x", anchor="w", pady=1)
            if emphasize_name:
                tk.Label(
                    row,
                    text=f"{index}. ",
                    background=background,
                    foreground=TEXT_PRIMARY,
                    font=("Segoe UI", 9),
                ).pack(side="left")
                tk.Label(
                    row,
                    text=name,
                    background=background,
                    foreground=TEXT_PRIMARY,
                    font=("Segoe UI", 11, "bold"),
                ).pack(side="left")
                suffix = f" — {count:,} LATE RECORDS"
            else:
                suffix = f"{index}. {name} — {count:,} LATE RECORDS"
            tk.Label(
                row,
                text=suffix,
                background=background,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI", 9),
            ).pack(side="left")

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

    def refresh_data(self):
        service = getattr(self.services, "attendance_ot_import_service", None)
        if service is None:
            return

        def preview_ready(plan):
            lines = ["REFRESH DATA PREVIEW", ""]
            for status, label in (
                ("NEW", "File baru"),
                ("CHANGED", "File berubah"),
                ("UNCHANGED", "File tidak berubah"),
                ("MISSING", "File tidak ditemukan"),
                ("ERROR", "File error"),
            ):
                items = tuple(item for item in plan.files if item.status == status)
                lines.append(f"{label}: {len(items)}")
                if status in {"NEW", "CHANGED", "MISSING", "ERROR"}:
                    lines.extend(
                        f"- [{item.source_type}] {item.filename}" for item in items
                    )
            lines.extend(("", "Lanjutkan Refresh Data?"))
            if not self.services.dialog_service.confirm(
                "Refresh Data", "\n".join(lines)
            ):
                self.progress_var.set("Refresh Data dibatalkan.")
                return
            self.run_task(
                lambda report: service.refresh(report, plan=plan),
                done,
                "Scanning files",
                reporting=True,
            )

        def done(result):
            self.progress_var.set(
                f"Completed | Processed {result.files_processed} | Skipped {result.files_skipped} | Error {result.files_error} | Rows {result.rows_imported:,}"
            )
            if result.files_processed or result.files_error or result.files_missing:
                message = (
                    "REFRESH COMPLETED WITH UPDATES\n\n"
                    f"Files processed: {result.files_processed}\n"
                    f"Files skipped: {result.files_skipped}\n"
                    f"Files error: {result.files_error}\n"
                    f"Rows imported: {result.rows_imported:,}"
                )
            else:
                message = (
                    "Refresh completed — no source file changes detected.\n\n"
                    f"Files checked: {result.files_discovered}\n"
                    f"Files unchanged: {result.files_skipped}"
                )
            self.services.dialog_service.info("Refresh Data", message)
            self.load_view(options=True)

        self.run_task(
            service.prepare_refresh,
            preview_ready,
            "Preparing refresh preview",
        )

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
            window.columnconfigure(0, weight=1)
            window.rowconfigure(0, weight=1)
            text = tk.Text(
                window,
                wrap="word",
                font=("Segoe UI", 10),
                background=CARD_BACKGROUND,
                foreground=TEXT_PRIMARY,
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
            actions = ttk.Frame(window)
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
            table = DataTable(window, columns, labels)
            table.grid(row=1, column=0, sticky="nsew", padx=12)
            table.rows(preview.samples, columns)

            actions = ttk.Frame(window)
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
        self.refresh_progress.start(12)
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

        def done(result):
            if self._disposed:
                return
            self._busy = False
            self._navigation_locked = False
            self.refresh_progress.stop()
            self._actions = [
                button for button in self._actions if button.winfo_exists()
            ]
            for button in self._actions:
                button.configure(state="normal")
            if result.success:
                self.progress_var.set(message + " completed")
                on_success(result.value)
            else:
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

    def can_navigate_away(self):
        return not self._navigation_locked

    def dispose(self):
        self._disposed = True
