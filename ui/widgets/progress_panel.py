"""Shared busy/progress presentation."""

from __future__ import annotations

from tkinter import ttk


class ProgressPanel(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent, style="CardBody.TFrame")
        self.columnconfigure(0, weight=1)
        self.stage_label = ttk.Label(
            self,
            text="Progress",
            style="CardTitle.TLabel",
        )
        self.stage_label.grid(row=0, column=0, sticky="w")
        self.label = ttk.Label(self, text="", style="CardBody.TLabel")
        self.label.grid(row=1, column=0, sticky="w", pady=(4, 6))
        self.progress = ttk.Progressbar(
            self,
            mode="indeterminate",
            style="Teal.Horizontal.TProgressbar",
        )
        self.progress.grid(row=2, column=0, sticky="ew")
        self.grid_remove()

    def start(self, message: str) -> None:
        self.label.configure(text=message)
        self.grid()
        self.progress.start(12)

    def stop(self) -> None:
        self.progress.stop()
        self.grid_remove()
