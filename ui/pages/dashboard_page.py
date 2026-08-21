"""Read-only Dashboard summaries and recent activity."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import (
    BORDER,
    ERROR,
    MAIN_BACKGROUND,
    OLD_GOLD,
    SKY_BLUE,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SUCCESS,
    TEXT_SECONDARY,
)
from ui.pages.base_page import BasePage
from ui.widgets import MetricCard, ModuleStatusCard, SectionHeader


class DashboardPage(BasePage):
    page_id = "dashboard"
    title = "Dashboard"
    subtitle = "Ringkasan aktivitas dan status aplikasi"
    icon_name = "dashboard.ico"
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self._loaded = False
        self._busy = False
        self._disposed = False
        self._visible = False
        self._activities = {}
        self._blink_job = None
        self._blink_phase = 0
        self._chomper_job = None
        self._chomper_x = 0
        self._chomper_mouth_open = True
        self._chomper_eaten_until = -1
        self._blink_styles = (
            "DashboardValue.TLabel",
            "DashboardValueBlink1.TLabel",
            "DashboardValueBlink2.TLabel",
            "DashboardValueBlink3.TLabel",
            "DashboardValueBlink4.TLabel",
            "DashboardValueBlink5.TLabel",
        )
        super().__init__(parent, context)

    def build_content(self) -> None:
        self.services = self.context.app_services
        container = ttk.Frame(self, style="OASK.TFrame")
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure((0, 1, 2, 3), weight=1, uniform="dashboard")
        container.rowconfigure(5, weight=1)

        actions = ttk.Frame(container, style="OASK.TFrame")
        actions.grid(row=0, column=3, sticky="e", pady=(0, SPACE_SM))
        self.chomper_canvas = tk.Canvas(
            container,
            height=30,
            background=MAIN_BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
        )
        self.chomper_canvas.grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, SPACE_SM)
        )
        self.chomper_canvas.bind("<Configure>", lambda _event: self._draw_chomper())
        self.refresh_button = ttk.Button(
            actions, text="Refresh", style="Primary.TButton", command=self.refresh
        )
        self.refresh_button.grid(row=0, column=0)

        self.summary_cards = {}
        for column, title in enumerate(
            ("Database Status", "Data Root Status", "Last Backup", "System Health")
        ):
            card = MetricCard(
                container, title=title, value_style="DashboardValue.TLabel"
            )
            card.grid(
                row=1,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else SPACE_SM, 0),
            )
            self.summary_cards[title] = card

        quick_start = ttk.Frame(
            container, style="CompactPanel.TFrame", padding=(12, 8)
        )
        quick_start.grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(SPACE_LG, 0)
        )
        quick_start.columnconfigure(0, weight=1)
        ttk.Label(
            quick_start,
            text="Mulai dari Settings > Storage & Database untuk membuat atau memilih Data Root dan database OAS-K.",
            style="CompactTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            quick_start,
            text="Setelah database valid, lanjut Import / Export konfigurasi, lalu jalankan Attendance, Outlook Revisi, HRIS, atau Utilities.",
            style="CompactText.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(
            quick_start,
            text="Buka Settings",
            style="CompactPrimary.TButton",
            command=lambda: self.context.navigate
            and self.context.navigate("settings"),
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        SectionHeader(container, "Module activity").grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(SPACE_LG, SPACE_SM)
        )
        self.module_cards = {}
        for column, title in enumerate(
            ("Attendance", "Outlook Revisi", "HRIS", "Utilities")
        ):
            card = ModuleStatusCard(
                container, title=title, value_style="DashboardValue.TLabel"
            )
            card.grid(
                row=4,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else SPACE_SM, 0),
            )
            self.module_cards[title.upper().replace(" ", "_")] = card

        activity = ttk.Frame(
            container, style="ContentCard.TFrame", padding=(SPACE_LG, SPACE_MD)
        )
        activity.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(SPACE_LG, 0))
        activity.columnconfigure(0, weight=1)
        activity.rowconfigure(1, weight=1)
        ttk.Label(activity, text="Recent Activity", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, SPACE_SM)
        )
        ttk.Button(
            activity,
            text="Open Selected Output",
            command=self.open_selected_output,
        ).grid(row=0, column=0, sticky="e", pady=(0, SPACE_SM))
        columns = ("time", "module", "status", "output")
        self.table = ttk.Treeview(activity, columns=columns, show="headings", height=4)
        for column, heading, width in (
            ("time", "Waktu", 155),
            ("module", "Modul", 130),
            ("status", "Status", 145),
            ("output", "Output", 320),
        ):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, stretch=True)
        self.table.tag_configure("activity_success", foreground=SUCCESS)
        self.table.tag_configure("activity_warning", foreground="#3F7A2D")
        self.table.tag_configure("activity_error", foreground=ERROR)
        self.table.tag_configure("activity_running", foreground=SKY_BLUE)
        self.table.tag_configure("activity_neutral", foreground=TEXT_SECONDARY)
        self.table.grid(row=1, column=0, sticky="nsew")
        self.table.bind("<Double-1>", lambda event: self.open_selected_output())
        self.empty = ttk.Label(
            activity,
            text="Belum ada riwayat proses. Refresh membaca history secara read-only.",
            style="CardText.TLabel",
        )

    def on_show(self) -> None:
        self._visible = True
        if not self._busy:
            self.refresh()
        self._start_chomper()

    def on_hide(self) -> None:
        self._visible = False
        self._stop_value_blink()
        self._stop_chomper()

    def refresh(self) -> None:
        if self._busy or self._disposed:
            return
        self._busy = True
        self.refresh_button.configure(state="disabled")
        self._status("Membaca Dashboard...")

        def done(result) -> None:
            if self._disposed:
                return
            self._busy = False
            self.refresh_button.configure(state="normal")
            if result.success:
                self._loaded = True
                self._render(result.value)
                self._status("Dashboard diperbarui")
            else:
                self._status("Dashboard gagal diperbarui")
                self.services.dialog_service.error("Dashboard", result.error or "Error")

        self.services.task_runner.submit(
            self.services.dashboard_service.get_dashboard_summary,
            on_done=done,
            cancellable=True,
        )

    def _render(self, summary) -> None:
        friendly = {
            "Invalid": "Needs attention",
            "INITIAL_SETUP_REQUIRED": "Setup needed",
            "RECOVERY_REQUIRED": "Recovery needed",
            "REGISTRY_UNAVAILABLE": "Registry unavailable",
            "AVAILABLE_NOT_REGISTERED": "Available",
            "NOT_CHECKED": "Not checked",
        }
        self.summary_cards["Database Status"].set(
            friendly.get(summary.database_status, summary.database_status)
        )
        self.summary_cards["Data Root Status"].set(
            friendly.get(summary.data_root_status, summary.data_root_status)
        )
        backup = summary.last_backup
        self.summary_cards["Last Backup"].set(
            backup.status if backup.available else "No backup",
            backup.occurred_at or "Belum ada backup",
        )
        system_health_status = self._effective_system_health_status(
            summary.system_health_status
        )
        self.summary_cards["System Health"].set(
            friendly.get(
                system_health_status,
                system_health_status.replace("_", " ").title(),
            )
        )
        for module in summary.modules:
            card = self.module_cards.get(module.module)
            if card is not None:
                card.set_summary(module)
        self.table.delete(*self.table.get_children())
        self._activities.clear()
        for item in summary.recent_activity:
            iid = self.table.insert(
                "",
                "end",
                values=(
                    item.occurred_at,
                    item.module,
                    item.status,
                    item.output_path or "—",
                ),
                tags=(self._activity_status_tag(item.status),),
            )
            self._activities[iid] = item
        if summary.recent_activity:
            self.empty.grid_remove()
            self.table.grid()
        else:
            self.table.grid_remove()
            self.empty.grid(row=1, column=0, sticky="w", pady=SPACE_SM)
        self._start_value_blink()

    def _effective_system_health_status(self, stored_status: str) -> str:
        health_service = getattr(self.services, "system_health_service", None)
        get_summary = getattr(health_service, "get_summary", None)
        if not callable(get_summary):
            return stored_status
        try:
            health_summary = get_summary()
        except Exception:
            return stored_status
        if not getattr(health_summary, "checked_at", None):
            return stored_status
        overall = getattr(health_summary, "overall", None)
        if overall is None:
            return stored_status
        return str(getattr(overall, "value", overall))

    @staticmethod
    def _activity_status_tag(status: str) -> str:
        normalized = status.upper()
        if normalized in {"COMPLETED", "UPLOADED"}:
            return "activity_success"
        if normalized in {"COMPLETED_WITH_WARNING", "WARNING"}:
            return "activity_warning"
        if normalized in {"FAILED", "ERROR"}:
            return "activity_error"
        if normalized == "RUNNING":
            return "activity_running"
        return "activity_neutral"

    def open_selected_output(self) -> None:
        selected = self.table.selection()
        item = self._activities.get(selected[0]) if selected else None
        if (
            item is None
            or item.output_path is None
            or not self.services.file_system_service.open_folder(item.output_path)
        ):
            self.services.dialog_service.warning(
                "Open Output", "Output folder tidak tersedia."
            )

    def _status(self, message: str) -> None:
        if self.context.set_status:
            self.context.set_status(message)

    def _start_value_blink(self) -> None:
        if self._disposed or not self._visible or self._blink_job is not None:
            return
        self._blink_phase = 0
        self._apply_value_blink_style()
        self._blink_job = self.after(140, self._advance_value_blink)

    def _advance_value_blink(self) -> None:
        self._blink_job = None
        if self._disposed:
            return
        self._blink_phase = (self._blink_phase + 1) % len(self._blink_styles)
        self._apply_value_blink_style()
        self._blink_job = self.after(140, self._advance_value_blink)

    def _apply_value_blink_style(self) -> None:
        style = self._blink_styles[self._blink_phase]
        for card in self.module_cards.values():
            card.value_label.configure(style=style)

    def _stop_value_blink(self) -> None:
        if self._blink_job is not None:
            try:
                self.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None
        self._blink_phase = 0
        if hasattr(self, "summary_cards") and hasattr(self, "module_cards"):
            for card in (*self.summary_cards.values(), *self.module_cards.values()):
                card.value_label.configure(style="DashboardValue.TLabel")

    def _start_chomper(self) -> None:
        if self._disposed or not self._visible or self._chomper_job is not None:
            return
        self._draw_chomper()
        self._chomper_job = self.after(90, self._advance_chomper)

    def _advance_chomper(self) -> None:
        self._chomper_job = None
        if self._disposed or not self._visible:
            return
        width = max(1, self.chomper_canvas.winfo_width())
        next_x = self._chomper_x + 5
        if next_x >= width + 28:
            next_x = 0
            self._chomper_eaten_until = -1
        self._chomper_x = next_x
        self._chomper_eaten_until = max(self._chomper_eaten_until, self._chomper_x)
        self._chomper_mouth_open = not self._chomper_mouth_open
        self._draw_chomper()
        self._chomper_job = self.after(90, self._advance_chomper)

    def _draw_chomper(self) -> None:
        if not hasattr(self, "chomper_canvas"):
            return
        canvas = self.chomper_canvas
        canvas.delete("chomper")
        height = max(24, canvas.winfo_height())
        y = height // 2
        radius = 9
        width = max(1, canvas.winfo_width())
        pellet_x = 18
        while pellet_x < width - 8:
            if pellet_x > self._chomper_eaten_until:
                canvas.create_oval(
                    pellet_x - 2,
                    y - 2,
                    pellet_x + 2,
                    y + 2,
                    fill=OLD_GOLD,
                    outline=OLD_GOLD,
                    tags="chomper",
                )
            pellet_x += 24
        x = self._chomper_x - radius
        if x < -radius:
            x = -radius
        canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=OLD_GOLD,
            outline=BORDER,
            width=2,
            tags="chomper",
        )
        mouth = 8 if self._chomper_mouth_open else 3
        canvas.create_polygon(
            x,
            y,
            x + radius + 2,
            y - mouth,
            x + radius + 2,
            y + mouth,
            fill=MAIN_BACKGROUND,
            outline=MAIN_BACKGROUND,
            tags="chomper",
        )
        canvas.create_oval(
            x + 1,
            y - 6,
            x + 4,
            y - 3,
            fill=BORDER,
            outline=BORDER,
            tags="chomper",
        )

    def _stop_chomper(self) -> None:
        if self._chomper_job is not None:
            try:
                self.after_cancel(self._chomper_job)
            except Exception:
                pass
            self._chomper_job = None
        self._chomper_eaten_until = -1
        if hasattr(self, "chomper_canvas"):
            self.chomper_canvas.delete("chomper")

    def dispose(self) -> None:
        self._disposed = True
        self._stop_value_blink()
        self._stop_chomper()
