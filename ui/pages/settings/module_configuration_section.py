"""Central, read-only active configuration summaries for four modules."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import MAIN_BACKGROUND
from ui.dialogs.module_configuration_detail import ModuleConfigurationDetailDialog
from ui.pages.settings.common import SettingsSection
from ui.widgets import ModernCard


class ModuleConfigurationSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self.cards = {}
        ttk.Label(
            self,
            text="Konfigurasi Modul",
            style="SectionHeader.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=(
                "Ringkasan konfigurasi aktif dari OAS-K Database. "
                "Halaman ini hanya membaca konfigurasi dan tidak menjalankan modul."
            ),
            wraplength=850,
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))
        viewport = ttk.Frame(self, style="OASK.TFrame")
        viewport.grid(row=2, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        canvas = tk.Canvas(
            viewport,
            highlightthickness=0,
            background=MAIN_BACKGROUND,
        )
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.card_frame = ttk.Frame(canvas, style="OASK.TFrame")
        window = canvas.create_window((0, 0), window=self.card_frame, anchor="nw")
        self.card_frame.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        self.card_frame.columnconfigure((0, 1), weight=1, uniform="module-card")
        refresh = ttk.Button(self, text="Refresh", command=self.refresh)
        refresh.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.page.register_action(refresh)
        self._show_placeholders()

    def on_selected(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        status = self.active_status()
        database = status.database_path if status.database_valid else None
        self.page.run_task(
            lambda: self.services.module_configuration_service.load_summaries(database),
            on_success=self._render,
            message="Membaca konfigurasi aktif...",
        )

    def _show_placeholders(self) -> None:
        self._render(())

    def _render(self, summaries) -> None:
        for child in self.card_frame.winfo_children():
            child.destroy()
        self.cards.clear()
        values = summaries or tuple(
            type("Placeholder", (), {
                "module": module,
                "title": title,
                "status_label": "Belum diperiksa",
                "source": "OAS-K Database",
                "fields": (),
                "last_updated": None,
                "warning": None,
            })()
            for module, title in (
                ("ATTENDANCE", "Attendance"),
                ("OUTLOOK_REVISI", "Outlook Revisi"),
                ("HRIS", "HRIS"),
                ("UTILITIES", "Utilities"),
            )
        )
        for index, summary in enumerate(values):
            container = ModernCard(self.card_frame, title=summary.title)
            container.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=(0, 6) if index % 2 == 0 else (6, 0),
                pady=6,
            )
            card = container.body
            card.columnconfigure(1, weight=1)
            rows = (("Status", summary.status_label), ("Sumber", summary.source), *summary.fields, ("Terakhir Diperbarui", summary.last_updated or "-"))
            for row, (label, value) in enumerate(rows):
                ttk.Label(card, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 10))
                value_style = (
                    "StatusWarning.TLabel"
                    if label == "Status" and "Perhatian" in str(value)
                    else "StatusError.TLabel"
                    if label == "Status" and str(value) in {"Tidak Valid", "Error"}
                    else "StatusReady.TLabel"
                    if label == "Status" and str(value) in {"Aktif", "Siap"}
                    else "CardBody.TLabel"
                )
                ttk.Label(card, text=str(value), wraplength=280, style=value_style).grid(row=row, column=1, sticky="nw")
            next_row = len(rows)
            if summary.warning:
                ttk.Label(card, text=summary.warning, style="CardStatus.TLabel", wraplength=390).grid(row=next_row, column=0, columnspan=2, sticky="w", pady=(6, 0))
                next_row += 1
            actions = ttk.Frame(card, style="CardBody.TFrame")
            actions.grid(row=next_row, column=0, columnspan=2, sticky="w", pady=(10, 0))
            for text, command in (
                ("Lihat Detail", lambda module=summary.module: self.show_detail(module)),
                ("Import Pembaruan", lambda module=summary.module: self.page.show_configuration_section(module=module)),
                ("Export", lambda: self.page.show_configuration_section(export=True)),
            ):
                button = ttk.Button(
                    actions,
                    text=text,
                    command=command,
                    style="SecondaryAction.TButton",
                )
                button.pack(side="left", padx=(0, 6))
                self.page.register_action(button)
            self.cards[summary.module] = container

    def show_detail(self, module: str) -> None:
        try:
            database = self.active_database()
        except RuntimeError as exc:
            self.services.dialog_service.warning("Konfigurasi Modul", str(exc))
            return
        self.page.run_task(
            lambda: self.services.module_configuration_service.load_detail(database, module),
            on_success=lambda detail: ModuleConfigurationDetailDialog(self, detail),
            message="Membaca detail konfigurasi...",
        )
