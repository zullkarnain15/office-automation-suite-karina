"""Text status indicator."""

from __future__ import annotations

from tkinter import ttk


class StatusBadge(ttk.Label):
    def __init__(self, parent, text: str = "Belum diperiksa") -> None:
        super().__init__(parent, text=text, style="CardStatus.TLabel")

    def set(self, text: str) -> None:
        self.configure(text=text)
