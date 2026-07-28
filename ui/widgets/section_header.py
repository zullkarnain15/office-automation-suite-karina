"""Compact section heading."""

from __future__ import annotations

from tkinter import ttk


class SectionHeader(ttk.Label):
    def __init__(self, parent, text: str) -> None:
        super().__init__(
            parent,
            text=text,
            style="SectionHeader.TLabel",
        )
