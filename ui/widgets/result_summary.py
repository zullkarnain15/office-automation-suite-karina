"""Structured multi-line result summary."""

from __future__ import annotations

from tkinter import ttk


class ResultSummary(ttk.Frame):
    def __init__(self, parent, *, wraplength: int = 760) -> None:
        super().__init__(
            parent,
            style="RPGShadow.TFrame",
            padding=(0, 0, 3, 3),
        )
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        panel = ttk.Frame(self, style="ContentCard.TFrame", padding=(14, 12))
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        self.label = ttk.Label(
            panel,
            text="Belum ada hasil.",
            style="ResultSummary.TLabel",
            justify="left",
            wraplength=wraplength,
        )
        self.label.grid(row=0, column=0, sticky="w")

    def show_lines(self, lines: list[str] | tuple[str, ...]) -> None:
        self.label.configure(text="\n".join(lines) or "Tidak ada detail.")
