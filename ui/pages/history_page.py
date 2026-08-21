"""Paged and filtered read-only History page."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.constants import (
    BORDER,
    CARD_BACKGROUND,
    CARD_BODY_FONT,
    IVORY_WHITE,
    ROYAL_BLUE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    TEXT_PRIMARY,
)
from ui.pages.base_page import BasePage
from ui.services.history_service import HistoryFilters
from ui.widgets import DateEntry, EmptyState, PaginationBar, iso_to_display


class HistoryPage(BasePage):
    page_id = "history"
    title = "History"
    subtitle = "Riwayat pekerjaan dan hasil proses aplikasi."
    icon_name = "history.ico"
    page_size = 25
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self.offset = 0
        self.total = 0
        self._loaded = False
        self._busy = False
        self._disposed = False
        self._jobs = {}
        super().__init__(parent, context)

    def build_content(self) -> None:
        self.services = self.context.app_services
        container = ttk.Frame(self, style="OASK.TFrame")
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        filters = ttk.Frame(container, style="ContentCard.TFrame", padding=SPACE_MD)
        filters.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_SM))
        self.module_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.from_entry = DateEntry(filters, textvariable=self.from_var, width=10)
        self.to_entry = DateEntry(filters, textvariable=self.to_var, width=10)
        fields = (
            (
                "Module",
                ttk.Combobox(
                    filters,
                    textvariable=self.module_var,
                    values=("", "ATTENDANCE", "OUTLOOK_REVISI", "HRIS", "UTILITIES"),
                    width=15,
                    state="readonly",
                ),
            ),
            (
                "Status",
                ttk.Combobox(
                    filters,
                    textvariable=self.status_var,
                    values=("", "COMPLETED", "FAILED", "RUNNING", "NEED_REVIEW"),
                    width=16,
                    state="readonly",
                ),
            ),
            ("Date From (MM/DD/YYYY)", self.from_entry),
            ("Date To (MM/DD/YYYY)", self.to_entry),
            ("Search", ttk.Entry(filters, textvariable=self.search_var, width=20)),
        )
        for column, (label, widget) in enumerate(fields):
            ttk.Label(filters, text=label, style="CardText.TLabel").grid(
                row=0, column=column, sticky="w", padx=(0, SPACE_SM)
            )
            widget.grid(row=1, column=column, sticky="ew", padx=(0, SPACE_SM))
        self.refresh_button = ttk.Button(
            filters, text="Refresh", style="Primary.TButton", command=self.apply_filters
        )
        self.refresh_button.grid(row=1, column=5, padx=(SPACE_SM, 0))
        ttk.Button(filters, text="Clear Filter", command=self.clear_filters).grid(
            row=1, column=6, padx=(SPACE_SM, 0)
        )

        body = ttk.Frame(container, style="ContentCard.TFrame", padding=SPACE_MD)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        columns = (
            "time",
            "module",
            "workflow",
            "status",
            "period",
            "output",
            "duration",
        )
        self.table = ttk.Treeview(body, columns=columns, show="headings", height=8)
        for column, heading, width in (
            ("time", "Waktu", 145),
            ("module", "Modul", 110),
            ("workflow", "Workflow", 85),
            ("status", "Status", 135),
            ("period", "Periode", 145),
            ("output", "Output", 230),
            ("duration", "Durasi", 80),
        ):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, stretch=True)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<Double-1>", lambda event: self.view_details())
        self.empty = EmptyState(
            body,
            title="Belum ada riwayat proses.",
            message="Sesuaikan filter atau pastikan database tersedia.",
        )

        actions = ttk.Frame(container, style="OASK.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(SPACE_SM, 0))
        ttk.Button(actions, text="Open Output", command=self.open_output).pack(
            side="left"
        )
        ttk.Button(actions, text="Open Log", command=self.open_log).pack(
            side="left", padx=SPACE_SM
        )
        ttk.Button(actions, text="Open Report", command=self.open_report).pack(
            side="left"
        )
        ttk.Button(actions, text="View Details", command=self.view_details).pack(
            side="left", padx=SPACE_SM
        )
        self.pagination = PaginationBar(actions, self.previous_page, self.next_page)
        self.pagination.pack(side="right")

    def on_show(self) -> None:
        if not self._loaded and not self._busy:
            self.refresh()

    def apply_filters(self) -> None:
        self.offset = 0
        self.refresh()

    def clear_filters(self) -> None:
        for variable in (
            self.module_var,
            self.status_var,
            self.from_var,
            self.to_var,
            self.search_var,
        ):
            variable.set("")
        self.apply_filters()

    def current_filters(self) -> HistoryFilters:
        return HistoryFilters(
            self.module_var.get() or None,
            self.status_var.get() or None,
            self.from_entry.get_iso(),
            self.to_entry.get_iso(),
            self.search_var.get().strip() or None,
        )

    def refresh(self) -> None:
        if self._busy or self._disposed:
            return
        try:
            current_filters = self.current_filters()
        except ValueError as exc:
            self.services.dialog_service.warning("Format Tanggal", str(exc))
            return
        self._busy = True
        self.refresh_button.configure(state="disabled")
        filters, offset = current_filters, self.offset

        def done(result) -> None:
            if self._disposed:
                return
            self._busy = False
            self.refresh_button.configure(state="normal")
            if result.success:
                self._loaded = True
                self._render(result.value)
            else:
                self.services.dialog_service.error("History", result.error or "Error")

        self.services.task_runner.submit(
            lambda: self.services.history_service.search(
                filters, limit=self.page_size, offset=offset
            ),
            on_done=done,
        )

    def _render(self, result) -> None:
        self.total = result.total
        self._jobs.clear()
        self.table.delete(*self.table.get_children())
        for job in result.items:
            iid = self.table.insert(
                "",
                "end",
                values=(
                    job.started_at or job.created_at,
                    job.module_code,
                    job.workflow or "—",
                    job.unified_status,
                    f"{iso_to_display(job.period_start_used) or '—'} – "
                    f"{iso_to_display(job.period_end_used) or '—'}",
                    job.output_path_used or "—",
                    f"{job.duration_seconds:.1f}s"
                    if job.duration_seconds is not None
                    else "—",
                ),
            )
            self._jobs[iid] = job
        self.pagination.update_state(
            offset=self.offset, limit=self.page_size, total=result.total
        )
        if result.items:
            self.empty.grid_remove()
            self.table.grid()
        else:
            self.table.grid_remove()
            self.empty.grid(row=0, column=0, sticky="nsew")

    def previous_page(self) -> None:
        self.offset = max(0, self.offset - self.page_size)
        self.refresh()

    def next_page(self) -> None:
        if self.offset + self.page_size < self.total:
            self.offset += self.page_size
            self.refresh()

    def _selected(self):
        selected = self.table.selection()
        return self._jobs.get(selected[0]) if selected else None

    def _open_path(self, path: str | None, label: str) -> None:
        if not path or not self.services.file_system_service.open_folder(Path(path)):
            self.services.dialog_service.warning(label, "Path tidak tersedia.")

    def open_output(self) -> None:
        job = self._selected()
        self._open_path(job.output_path_used if job else None, "Open Output")

    def open_log(self) -> None:
        job = self._selected()
        self._open_path(job.process_log_path if job else None, "Open Log")

    def open_report(self) -> None:
        job = self._selected()
        self._open_path(job.summary_json_path if job else None, "Open Report")

    def view_details(self) -> None:
        job = self._selected()
        if job is None:
            self.services.dialog_service.warning("History Detail", "Pilih satu job.")
            return
        detail = self.services.history_service.get_job_detail(
            job.module_code, job.job_id
        )
        if detail is None:
            self.services.dialog_service.warning(
                "History Detail", "Detail tidak tersedia."
            )
            return
        window = tk.Toplevel(self)
        window.title("Job Detail")
        window.geometry("760x520")
        window.transient(self)
        text = tk.Text(
            window,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            selectbackground=ROYAL_BLUE,
            selectforeground=IVORY_WHITE,
            font=CARD_BODY_FONT,
            relief="solid",
            borderwidth=2,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            padx=SPACE_LG,
            pady=SPACE_LG,
        )
        text.pack(fill="both", expand=True)
        values = detail.job
        lines = [
            f"Job ID: {values.job_id}",
            f"Module: {values.module_code}",
            f"Workflow: {values.workflow or '—'}",
            f"Status: {values.unified_status}",
            f"Start: {values.started_at or '—'}",
            f"End: {values.finished_at or '—'}",
            f"Duration: {values.duration_seconds or '—'}",
            f"Period: {iso_to_display(values.period_start_used) or '—'} – "
            f"{iso_to_display(values.period_end_used) or '—'}",
            f"Output: {values.output_path_used}",
            f"Used global output: {values.used_global_output}",
            f"Used global period: {values.used_global_period}",
            f"Error summary: {values.error_message or '—'}",
            "",
            "Files:",
            *(f"- {item['file_role']}: {item['file_path']}" for item in detail.files),
            "",
            "Status events:",
            *(
                f"- {item['occurred_at']} [{item['unified_status']}] {item['message'] or ''}"
                for item in detail.events
            ),
        ]
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def dispose(self) -> None:
        self._disposed = True
