"""Three-step presentation indicator without workflow logic."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_SM


class StepIndicator(ttk.Frame):
    def __init__(self, parent, labels: tuple[str, ...]) -> None:
        super().__init__(parent, style="ContentCard.TFrame")
        self.labels = []
        for column, label in enumerate(labels):
            item = ttk.Label(
                self,
                text=f"{column + 1}. {label}",
                style="StepPending.TLabel",
            )
            item.grid(row=0, column=column, padx=(0, SPACE_SM), sticky="w")
            self.labels.append(item)
        self.set_step(0)

    def set_step(self, active: int) -> None:
        for index, label in enumerate(self.labels):
            style = (
                "StepCompleted.TLabel"
                if index < active
                else "StepActive.TLabel"
                if index == active
                else "StepPending.TLabel"
            )
            label.configure(style=style)
