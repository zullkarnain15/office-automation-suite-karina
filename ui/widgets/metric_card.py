"""Compact metric and module summary cards."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_LG, SPACE_SM, SPACE_XS


class MetricCard(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        value: str = "-",
        detail: str = "",
        value_style: str = "CardValue.TLabel",
    ):
        super().__init__(parent, style="RPGShadow.TFrame", padding=(0, 0, 3, 3))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.panel = ttk.Frame(
            self, style="ContentCard.TFrame", padding=(SPACE_LG, SPACE_LG)
        )
        self.panel.grid(row=0, column=0, sticky="nsew")
        self.panel.columnconfigure(0, weight=1)
        ttk.Label(self.panel, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="ew"
        )
        self.value_label = ttk.Label(
            self.panel,
            text=value,
            style=value_style,
            wraplength=210,
            justify="left",
        )
        self.value_label.grid(row=1, column=0, sticky="w", pady=(SPACE_SM, 2))
        self.detail_label = ttk.Label(
            self.panel, text=detail, style="CardText.TLabel", wraplength=260
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
    def __init__(
        self,
        parent,
        *,
        title: str,
        value: str = "-",
        detail: str = "",
        value_style: str = "CardValue.TLabel",
    ):
        super().__init__(
            parent,
            title=title,
            value=value,
            detail=detail,
            value_style=value_style,
        )
        self.detail_label.grid_remove()
        self.detail_frame = ttk.Frame(self.panel, style="CardBody.TFrame")
        self.detail_frame.grid(row=2, column=0, sticky="ew")
        self.detail_frame.columnconfigure(3, weight=1)
        self.success_label = ttk.Label(
            self.detail_frame, style="ModuleSuccess.TLabel"
        )
        self.success_label.grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.detail_frame, text="  .  ", style="ModuleDetail.TLabel"
        ).grid(row=0, column=1, sticky="w")
        self.failure_label = ttk.Label(self.detail_frame, style="ModuleError.TLabel")
        self.failure_label.grid(row=0, column=2, sticky="w")
        self.last_run_label = ttk.Label(
            self.detail_frame, style="ModuleDetail.TLabel", wraplength=260
        )
        self.last_run_label.grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(SPACE_XS, 0)
        )
        self.status_label = ttk.Label(
            self.detail_frame, style="ModuleNeutral.TLabel", wraplength=260
        )
        self.status_label.grid(row=2, column=0, columnspan=4, sticky="w")

    def _resize_text(self, event) -> None:
        super()._resize_text(event)
        wrap = max(120, event.width - 32)
        self.last_run_label.configure(wraplength=wrap)
        self.status_label.configure(wraplength=wrap)

    def set_summary(self, summary) -> None:
        status = summary.last_status.replace("_", " ").title()
        self.value_label.configure(text=str(summary.total))
        self.success_label.configure(text=f"Sukses {summary.succeeded}")
        self.failure_label.configure(text=f"Gagal {summary.failed}")
        self.last_run_label.configure(text=f"Terakhir: {summary.last_run or '-'}")
        self.status_label.configure(
            text=f"Status: {status}",
            style=self._status_style(summary.last_status),
        )

    @staticmethod
    def _status_style(status: str) -> str:
        normalized = status.upper()
        if normalized in {"COMPLETED", "UPLOADED"}:
            return "ModuleSuccess.TLabel"
        if normalized in {"COMPLETED_WITH_WARNING", "WARNING"}:
            return "ModuleWarning.TLabel"
        if normalized in {"FAILED", "ERROR"}:
            return "ModuleError.TLabel"
        if normalized == "RUNNING":
            return "ModuleRunning.TLabel"
        return "ModuleNeutral.TLabel"
