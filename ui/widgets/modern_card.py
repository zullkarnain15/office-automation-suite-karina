"""Lightweight bordered card with optional accent and a stable content area."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_LG, SPACE_SM


class ModernCard(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        accent: bool = True,
        padding: int = SPACE_LG,
    ) -> None:
        super().__init__(parent, style="ModernCard.TFrame")
        self.columnconfigure(0, weight=1)
        if accent:
            ttk.Frame(self, style="CardAccent.TFrame", height=3).grid(
                row=0,
                column=0,
                sticky="ew",
            )
        header_row = 1 if accent else 0
        ttk.Label(self, text=title, style="CardTitle.TLabel").grid(
            row=header_row,
            column=0,
            sticky="w",
            padx=padding,
            pady=(padding, SPACE_SM),
        )
        self.body = ttk.Frame(
            self,
            style="CardBody.TFrame",
            padding=(padding, 0, padding, padding),
        )
        self.body.grid(row=header_row + 1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.rowconfigure(header_row + 1, weight=1)
