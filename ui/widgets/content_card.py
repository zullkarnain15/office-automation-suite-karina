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
            style="ContentCard.TFrame",
            padding=(18, 16),
        )
        self.columnconfigure(0, weight=1)
        ttk.Label(
            self,
            text=title,
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=description,
            style="CardText.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="w", pady=(7, 12))
        ttk.Label(
            self,
            text=status,
            style="CardStatus.TLabel",
        ).grid(row=2, column=0, sticky="w")
