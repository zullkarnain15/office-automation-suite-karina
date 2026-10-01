"""Non-operational application status bar."""

from __future__ import annotations

from tkinter import ttk

from ui.models import StatusMetadata


class StatusBar(ttk.Frame):
    def __init__(self, parent, application_version: str) -> None:
        super().__init__(
            parent,
            style="StatusBar.TFrame",
            padding=(14, 7),
        )
        self.columnconfigure(0, weight=1)
        self.message_label = ttk.Label(
            self,
            text="Ready",
            style="StatusBar.TLabel",
        )
        self.message_label.grid(row=0, column=0, sticky="w")
        self.storage_label = ttk.Label(
            self,
            text="Database: Belum diperiksa",
            style="StatusBar.TLabel",
        )
        self.storage_label.grid(row=0, column=1, padx=(16, 0))
        self.version_label = ttk.Label(
            self,
            text=f"Versi {application_version}",
            style="StatusBar.TLabel",
        )
        self.version_label.grid(row=0, column=2, padx=(16, 0))

    def update_metadata(self, metadata: StatusMetadata) -> None:
        self.message_label.configure(
            text=f"{metadata.message} | {metadata.selected_page}"
        )
        self.storage_label.configure(text=metadata.storage_status)

    def set_message(self, message: str) -> None:
        self.message_label.configure(text=message)
