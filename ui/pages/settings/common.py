"""Shared Settings section helpers."""

from __future__ import annotations

from pathlib import Path
from tkinter import ttk


class SettingsSection(ttk.Frame):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, style="OASK.TFrame", padding=(16, 14))
        self.page = page
        self.services = page.services
        self.columnconfigure(0, weight=1)

    def action_button(self, *, text: str, command, row: int, column: int = 0):
        button = ttk.Button(
            self,
            text=text,
            command=command,
            style="Secondary.TButton",
        )
        button.grid(row=row, column=column, sticky="w", padx=(0, 8), pady=4)
        self.page.register_action(button)
        return button

    def active_status(self):
        return self.services.storage_service.resolve_status()

    def active_database(self) -> Path:
        status = self.active_status()
        if status.database_path is None or not status.database_valid:
            raise RuntimeError("Database aktif belum tersedia atau tidak valid.")
        return status.database_path

    def active_data_root(self) -> Path:
        status = self.active_status()
        if status.data_root is None:
            raise RuntimeError("Data Root aktif belum tersedia.")
        return status.data_root
