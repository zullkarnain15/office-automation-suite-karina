"""Consistent visual card for one health result."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_LG, SPACE_SM


class HealthStatusCard(ttk.Frame):
    def __init__(self, parent, *, title: str):
        super().__init__(
            parent, style="RPGShadow.TFrame", padding=(0, 0, 3, 3)
        )
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        panel = ttk.Frame(
            self,
            style="ContentCard.TFrame",
            padding=(SPACE_LG, SPACE_LG),
        )
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="ew"
        )
        self.status_label = ttk.Label(
            panel, text="NOT_CHECKED", style="CardStatus.TLabel"
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(SPACE_SM, 3))
        self.summary_label = ttk.Label(
            panel, text="Belum diperiksa.", style="CardText.TLabel", wraplength=300
        )
        self.summary_label.grid(row=2, column=0, sticky="w")

    def set_result(self, result) -> None:
        status = str(result.status)
        style = {
            "HEALTHY": "HealthHealthy.TLabel",
            "WARNING": "HealthWarning.TLabel",
            "ERROR": "HealthError.TLabel",
        }.get(status, "CardStatus.TLabel")
        self.status_label.configure(text=status, style=style)
        self.summary_label.configure(text=result.summary)
