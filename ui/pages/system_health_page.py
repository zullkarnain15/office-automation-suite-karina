"""Explicit read-only System Health checks."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import MAIN_BACKGROUND, SPACE_SM
from ui.pages.base_page import BasePage
from ui.widgets import HealthStatusCard


HEALTH_CARDS = (
    ("database", "Database"),
    ("data_root", "Data Root"),
    ("registry", "Registry Pointer"),
    ("backup", "Backup Folder"),
    ("profiles", "Recorder Profiles"),
    ("output", "Output Folder"),
    ("logs", "Logs Folder"),
    ("diagnostics", "Diagnostics Folder"),
    ("attendance", "Attendance Readiness"),
    ("outlook", "Outlook Revisi Readiness"),
    ("hris", "HRIS Readiness"),
    ("utilities", "Utilities Readiness"),
    ("write_access", "Write Access"),
    ("recovery", "Recovery Status"),
)


class SystemHealthPage(BasePage):
    page_id = "system_health"
    title = "System Health"
    subtitle = "Status kesiapan komponen aplikasi."
    icon_name = "system_health.ico"
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self._busy = False
        self._disposed = False
        super().__init__(parent, context)

    def build_content(self) -> None:
        self.services = self.context.app_services
        container = ttk.Frame(self, style="OASK.TFrame")
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        actions = ttk.Frame(container, style="OASK.TFrame")
        actions.grid(row=0, column=0, sticky="e", pady=(0, SPACE_SM))
        self.run_button = ttk.Button(
            actions,
            text="Run Checks",
            style="AttendancePrimary.TButton",
            command=self.run_checks,
        )
        self.run_button.pack(side="left")
        ttk.Button(
            actions, text="Open Diagnostics", command=self.open_diagnostics
        ).pack(side="left", padx=(SPACE_SM, 0))

        viewport = ttk.Frame(container, style="OASK.TFrame")
        viewport.grid(row=1, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        canvas = tk.Canvas(
            viewport,
            background=MAIN_BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        cards_frame = ttk.Frame(canvas, style="OASK.TFrame")
        window_id = canvas.create_window((0, 0), window=cards_frame, anchor="nw")
        cards_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        for column in range(4):
            cards_frame.columnconfigure(column, weight=1, uniform="health")
        self.cards = {}
        for index, (code, title) in enumerate(HEALTH_CARDS):
            card = HealthStatusCard(cards_frame, title=title)
            card.grid(
                row=index // 4 + 1,
                column=index % 4,
                sticky="nsew",
                padx=(0 if index % 4 == 0 else SPACE_SM, 0),
                pady=(0, SPACE_SM),
            )
            self.cards[code] = card

    def on_show(self) -> None:
        # Deliberately show cached/in-memory state; never auto-run checks.
        for result in self.services.system_health_service.get_last_result():
            if result.code in self.cards:
                self.cards[result.code].set_result(result)

    def run_checks(self) -> None:
        if self._busy or self._disposed:
            return
        self._busy = True
        self.run_button.configure(state="disabled")

        def done(result) -> None:
            if self._disposed:
                return
            self._busy = False
            self.run_button.configure(state="normal")
            if result.success:
                for item in result.value:
                    if item.code in self.cards:
                        self.cards[item.code].set_result(item)
            else:
                self.services.dialog_service.error(
                    "System Health", result.error or "Error"
                )

        self.services.task_runner.submit(
            self.services.system_health_service.run_all_checks,
            on_done=done,
        )

    def open_diagnostics(self) -> None:
        status = self.services.storage_service.resolve_status()
        path = status.diagnostics_folder
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Diagnostics", "Folder diagnostics tidak tersedia."
            )

    def dispose(self) -> None:
        self._disposed = True
