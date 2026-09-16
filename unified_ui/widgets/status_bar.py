"""Bottom application status bar."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    """Display shell, database, and version status."""

    def __init__(
        self,
        parent: ttk.Frame,
        version: str,
    ) -> None:
        super().__init__(
            parent,
            style="Status.TFrame",
            padding=(14, 7),
            relief="solid",
            borderwidth=1,
        )
        self.status = tk.StringVar(self, value="Status: Ready")
        self.database = tk.StringVar(self, value="Database: Not initialized")

        self.columnconfigure(1, weight=1)
        ttk.Label(
            self,
            textvariable=self.status,
            style="StatusStrong.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            textvariable=self.database,
            style="Status.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(28, 0))
        ttk.Label(
            self,
            text=f"Version: {version}",
            style="Status.TLabel",
        ).grid(row=0, column=2, sticky="e")

    def set_status(self, message: str) -> None:
        """Update the shell status text."""

        self.status.set(f"Status: {message}")
