"""Action chooser for portable Attendance & OT database operations."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import CARD_BACKGROUND, CARD_BODY_FONT, TEXT_PRIMARY


class AttendanceOTDatabaseManagerDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        *,
        on_validate,
        on_export,
        on_import,
    ) -> None:
        super().__init__(parent)
        self.title("Kelola Database ATTENDANCE & OT")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)

        frame = ttk.Frame(self, style="OASK.TFrame", padding=18)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        ttk.Label(
            frame,
            text="Database ATTENDANCE & OT",
            style="SectionHeader.TLabel",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            frame,
            text=(
                "Validasi file dari PC lain, buat backup portable, atau ganti "
                "database analytics aktif melalui staging dan rollback otomatis.\n\n"
                "Database core dan konfigurasi folder source lokal tidak diubah."
            ),
            justify="left",
            wraplength=580,
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=CARD_BODY_FONT,
        ).grid(row=1, column=0, sticky="ew", pady=(10, 16))

        actions = ttk.Frame(frame, style="OASK.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        self._action_button(
            actions,
            "Validasi File",
            on_validate,
            0,
        )
        self._action_button(
            actions,
            "Export Backup Terverifikasi",
            on_export,
            1,
        )
        self._action_button(
            actions,
            "Import / Ganti Database Aktif",
            on_import,
            2,
        )
        ttk.Button(frame, text="Tutup", command=self.destroy).grid(
            row=3, column=0, sticky="e", pady=(16, 0)
        )
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _action_button(self, parent, text, callback, column: int) -> None:
        ttk.Button(
            parent,
            text=text,
            command=lambda: self._choose(callback),
        ).grid(row=0, column=column, sticky="ew", padx=4)

    def _choose(self, callback) -> None:
        self.destroy()
        callback()
