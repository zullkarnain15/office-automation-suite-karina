"""Reusable descriptive empty state."""

from __future__ import annotations

from tkinter import ttk


class EmptyState(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        message: str,
    ) -> None:
        super().__init__(
            parent,
            style="ContentCard.TFrame",
            padding=(28, 26),
        )
        self.columnconfigure(0, weight=1)
        ttk.Label(
            self,
            text=title,
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self,
            text=message,
            style="EmptyState.TLabel",
            justify="left",
            wraplength=720,
        ).grid(row=1, column=0, sticky="w", pady=(10, 0))
