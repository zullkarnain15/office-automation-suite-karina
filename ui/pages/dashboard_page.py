"""Read-only Dashboard summaries and recent activity."""

from __future__ import annotations

from tkinter import ttk

from ui.constants import SPACE_LG, SPACE_MD, SPACE_SM
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
        self._activities = {}
        super().__init__(parent, context)

    def build_content(self) -> None:
        self.services = self.context.app_services
        container = ttk.Frame(self, style="OASK.TFrame")
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure((0, 1, 2, 3), weight=1, uniform="dashboard")
        container.rowconfigure(5, weight=1)

        actions = ttk.Frame(container, style="OASK.TFrame")
        actions.grid(row=0, column=0, columnspan=4, sticky="e", pady=(0, SPACE_SM))
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
        self.table.grid(row=1, column=0, sticky="nsew")
        self.table.bind("<Double-1>", lambda event: self.open_selected_output())
        self.empty = ttk.Label(
            activity,
            text="Belum ada riwayat proses. Refresh membaca history secara read-only.",
            style="CardText.TLabel",
        )

    def on_show(self) -> None:
        if not self._loaded and not self._busy:
            self.refresh()

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
        self.summary_cards["System Health"].set(
            friendly.get(
                summary.system_health_status,
                summary.system_health_status.replace("_", " ").title(),
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
            )
            self._activities[iid] = item
        if summary.recent_activity:
            self.empty.grid_remove()
            self.table.grid()
        else:
            self.table.grid_remove()
            self.empty.grid(row=1, column=0, sticky="w", pady=SPACE_SM)

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

    def dispose(self) -> None:
        self._disposed = True
