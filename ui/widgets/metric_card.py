"""Compact metric and module summary cards."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_LG, SPACE_SM


class MetricCard(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        value: str = "—",
        detail: str = "",
        value_style: str = "CardValue.TLabel",
    ):
        super().__init__(
            parent, style="ContentCard.TFrame", padding=(SPACE_LG, SPACE_LG)
        )
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.value_label = ttk.Label(
            self,
            text=value,
            style=value_style,
            wraplength=210,
            justify="left",
        )
        self.value_label.grid(row=1, column=0, sticky="w", pady=(SPACE_SM, 2))
        self.detail_label = ttk.Label(
            self, text=detail, style="CardText.TLabel", wraplength=260
        )
        self.detail_label.grid(row=2, column=0, sticky="w")
        self.bind("<Configure>", self._resize_text)

    def _resize_text(self, event) -> None:
        wrap = max(120, event.width - 32)
        self.value_label.configure(wraplength=wrap)
        self.detail_label.configure(wraplength=wrap)

    def set(self, value: str, detail: str = "") -> None:
        self.value_label.configure(text=value)
        self.detail_label.configure(text=detail)


class ModuleStatusCard(MetricCard):
    def set_summary(self, summary) -> None:
        status = summary.last_status.replace("_", " ").title()
        self.set(
            str(summary.total),
            f"Sukses {summary.succeeded}  •  Gagal {summary.failed}\n"
            f"Terakhir: {summary.last_run or '—'}\nStatus: {status}",
        )
