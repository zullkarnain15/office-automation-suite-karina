"""Always-visible, stage-based compact progress presentation."""

from __future__ import annotations

from tkinter import ttk


class CompactProgress(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent, style="CompactBody.TFrame")
        self.columnconfigure(2, weight=1)
        ttk.Label(self, text="Progress", style="CompactTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.label = ttk.Label(self, text="Status: Siap", style="CompactText.TLabel")
        self.label.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.progress = ttk.Progressbar(
            self, mode="indeterminate", style="Teal.Horizontal.TProgressbar"
        )
        self.progress.grid(row=0, column=2, sticky="ew", padx=(12, 0))

    def start(self, message: str) -> None:
        self.label.configure(text=message)
        self.progress.start(12)

    def stop(self) -> None:
        self.progress.stop()
        self.label.configure(text="Status: Siap")
