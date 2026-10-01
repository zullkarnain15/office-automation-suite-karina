"""Consistent label/control form row."""

from __future__ import annotations

from tkinter import ttk


class FormRow(ttk.Frame):
    def __init__(self, parent, label: str) -> None:
        super().__init__(parent, style="OASK.TFrame")
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=label, style="SectionHeader.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 12),
        )
