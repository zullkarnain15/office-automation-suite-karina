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
        super().__init__(parent, style="RPGShadow.TFrame", padding=(0, 0, 3, 3))
        self.columnconfigure(0, weight=1)
        panel = ttk.Frame(self, style="ModernCard.TFrame")
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        if accent:
            ttk.Frame(panel, style="CardAccent.TFrame", height=3).grid(
                row=0,
                column=0,
                sticky="ew",
            )
        header_row = 1 if accent else 0
        ttk.Label(panel, text=title, style="CardTitle.TLabel").grid(
            row=header_row,
            column=0,
            sticky="ew",
            padx=padding,
            pady=(padding, SPACE_SM),
        )
        self.body = ttk.Frame(
            panel,
            style="CardBody.TFrame",
            padding=(padding, 0, padding, padding),
        )
        self.body.grid(row=header_row + 1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        panel.rowconfigure(header_row + 1, weight=1)
