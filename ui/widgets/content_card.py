"""Simple professional content card."""

from __future__ import annotations

from tkinter import ttk


class ContentCard(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        description: str,
        status: str = "Belum diintegrasikan",
    ) -> None:
        super().__init__(
            parent,
            style="RPGShadow.TFrame",
            padding=(0, 0, 3, 3),
        )
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        panel = ttk.Frame(self, style="ContentCard.TFrame", padding=(18, 16))
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        ttk.Label(
            panel,
            text=title,
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            panel,
            text=description,
            style="CardText.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="w", pady=(7, 12))
        ttk.Label(
            panel,
            text=status,
            style="CardStatus.TLabel",
        ).grid(row=2, column=0, sticky="w")
