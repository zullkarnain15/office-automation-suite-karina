"""Application header widget."""

from __future__ import annotations

from tkinter import ttk


class Header(ttk.Frame):
    """Compact OAS-K title and company header."""

    def __init__(self, parent: ttk.Frame) -> None:
        super().__init__(parent, style="Header.TFrame", padding=(24, 13))
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text="Office Automation Suite - Karina",
            style="HeaderTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text="Unified Office Automation",
            style="HeaderSubtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(
            self,
            text="OTO Finance",
            style="HeaderCompany.TLabel",
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(18, 0))
