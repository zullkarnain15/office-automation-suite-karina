"""Three-tab GUI for the isolated Finger Monitoring module."""

from __future__ import annotations

import ipaddress
import queue
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import ttk

from ui.pages.base_page import BasePage
from ui.theme.finger_monitoring import apply_finger_monitoring_styles, finger_palette
from ui.theme.palette import palette
from ui.widgets import DateEntry, PaginationBar, TreeviewCopyHelper


class FingerMonitoringPage(BasePage):
    page_id = "finger_monitoring"
    title = "Finger Monitoring"
    subtitle = "Monitoring perangkat fingerprint berbasis IP."
    icon_name = "fp_monitoring.ico"
    show_page_heading = False
    history_page_size = 100
    online_blink_interval_ms = 700

    def __init__(self, parent, context):
        self._event_job = None
        self._online_blink_job = None
        self._online_blink_is_dim = False
        self._busy = False
        self.history_offset = 0
        self._tree_sort_state = {}
        self._tree_heading_labels = {}
        self._status_rows = ()
        self._master_rows = ()
        self._backup_rows = ()
        self._backup_snapshot = None
        self._backup_progress_queue = queue.SimpleQueue()
        self._backup_settings_requested = False
        self._history_sort_by = "checked_at"
        self._history_sort_descending = True
        self._cycle_total = 0
        self._cycle_checked = 0
        self._refresh_inflight = set()
        self._refresh_latest = {}
        super().__init__(parent, context)

    def build_content(self):
        self.services = self.context.app_services
        self.service = self.services.finger_monitoring_service
        apply_finger_monitoring_styles(self)
        self.configure(style="FingerMonitoringPage.TFrame")
        self.rowconfigure(1, weight=1); self.columnconfigure(0, weight=1)
        self._scene = tk.Canvas(
            self,
            height=82,
            background=finger_palette.sky,
            highlightthickness=0,
            borderwidth=0,
        )
        self._scene.grid(row=0, column=0, sticky="ew")
        self._scene.bind("<Configure>", self._draw_retro_scene)
        self.notebook = ttk.Notebook(self, style="FingerMonitoring.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.status_tab = self._tab("DEVICE STATUS")
        self.master_tab = self._tab("DEVICE MASTER")
        self.history_tab = self._tab("HISTORY")
        self.backup_tab = self._tab("MONITORING BACKUP MDB")
        self._build_status(); self._build_master(); self._build_history(); self._build_backup()

    def _tab(self, name):
        frame = ttk.Frame(self.notebook, style="FingerMonitoringSurface.TFrame", padding=10)
        self.notebook.add(frame, text=name)
        return frame

    def _draw_retro_scene(self, event=None):
        """Render a small, original pixel scene as module decoration."""

        scene = self._scene
        width = max(scene.winfo_width(), 640)
        height = max(scene.winfo_height(), 82)
        colors = finger_palette
        scene.delete("all")
        scene.create_rectangle(0, 0, width, height, fill=colors.sky, outline="")

        for x, y in ((40, 16), (width // 2 - 50, 10), (width - 265, 22)):
            scene.create_rectangle(x, y + 7, x + 55, y + 18, fill=colors.cloud, outline="")
            scene.create_rectangle(x + 12, y, x + 38, y + 24, fill=colors.cloud, outline="")
            scene.create_rectangle(x + 39, y + 5, x + 67, y + 19, fill=colors.cloud, outline="")

        scene.create_text(
            22,
            35,
            anchor="w",
            text="FINGER MONITORING",
            fill=colors.ink,
            font=("Segoe UI", 15, "bold"),
        )
        mushroom_x, mushroom_y = width - 112, 14
        scene.create_rectangle(mushroom_x + 13, mushroom_y + 34, mushroom_x + 29, mushroom_y + 55, fill=colors.cloud, outline=colors.ink)
        scene.create_rectangle(mushroom_x + 3, mushroom_y + 23, mushroom_x + 39, mushroom_y + 39, fill=colors.brick, outline=colors.ink)
        scene.create_rectangle(mushroom_x + 9, mushroom_y + 16, mushroom_x + 33, mushroom_y + 23, fill=colors.brick, outline=colors.ink)
        scene.create_rectangle(mushroom_x + 10, mushroom_y + 26, mushroom_x + 16, mushroom_y + 32, fill=colors.cloud, outline="")
        scene.create_rectangle(mushroom_x + 28, mushroom_y + 27, mushroom_x + 34, mushroom_y + 33, fill=colors.cloud, outline="")

        ground_y = height - 22
        scene.create_rectangle(0, ground_y, width, height, fill=colors.brick, outline=colors.ink)
        for x in range(-24, width + 24, 48):
            scene.create_line(x, ground_y, x, height, fill=colors.ink, width=1)
            scene.create_line(x + 24, ground_y + 11, x + 24, height, fill=colors.ink, width=1)
        scene.create_line(0, ground_y + 11, width, ground_y + 11, fill=colors.ink, width=1)

    def _button(self, parent, text, command, *, danger=False):
        accents = {
            "Check All Now": "FingerMonitoringMint.TButton",
            "Check Selected": "FingerMonitoringPurple.TButton",
            "Add": "FingerMonitoringMint.TButton",
            "Edit": "FingerMonitoring.TButton",
            "Reactivate": "FingerMonitoringPurple.TButton",
            "Import Excel": "FingerMonitoringOrange.TButton",
            "Template": "FingerMonitoringYellow.TButton",
            "Export": "FingerMonitoringMint.TButton",
            "Export Excel": "FingerMonitoringMint.TButton",
            "Cek Backup": "FingerMonitoringPurple.TButton",
            "Simpan Pengaturan": "FingerMonitoringMint.TButton",
            "Kirim Email": "FingerMonitoringOrange.TButton",
            "Save": "FingerMonitoringMint.TButton",
        }
        style = "FingerMonitoringDanger.TButton" if danger else accents.get(text, "FingerMonitoring.TButton")
        return ttk.Button(parent, text=text, command=command, style=style)

    def _build_status(self):
        tab = self.status_tab; tab.columnconfigure(0, weight=1); tab.rowconfigure(3, weight=1)
        kpis = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); kpis.grid(row=0, column=0, sticky="ew")
        self.kpi_vars = {name: tk.StringVar(value="0") for name in ("Total", "Online", "Offline", "Alert ≥3 Days")}
        self.kpi_cards = {}
        card_styles = {
            "Total": "Total",
            "Online": "Online",
            "Offline": "Offline",
            "Alert ≥3 Days": "Alert",
        }
        for index, (name, variable) in enumerate(self.kpi_vars.items()):
            style_name = f"FingerMonitoring{card_styles[name]}Card"
            card = ttk.Frame(kpis, style=f"{style_name}.TFrame", padding=9)
            card.grid(row=0, column=index, sticky="ew", padx=(0, 7))
            ttk.Label(card, text=name, style=f"{style_name}.TLabel").pack(anchor="w")
            ttk.Label(
                card,
                textvariable=variable,
                style=f"{style_name}.TLabel",
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w")
            self.kpi_cards[name] = card
            kpis.columnconfigure(index, weight=1)
        filters = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); filters.grid(row=1, column=0, sticky="ew", pady=8)
        self.status_search = tk.StringVar(); self.status_filter = tk.StringVar(value="ALL"); self.status_model = tk.StringVar(value="ALL")
        for label, widget in (("Search", ttk.Entry(filters, textvariable=self.status_search, width=23, style="FingerMonitoring.TEntry")), ("Status", ttk.Combobox(filters, textvariable=self.status_filter, values=("ALL", "ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR"), state="readonly", width=21, style="FingerMonitoring.TCombobox")), ("Model", ttk.Entry(filters, textvariable=self.status_model, width=16, style="FingerMonitoring.TEntry"))):
            ttk.Label(filters, text=label, style="FingerMonitoringBody.TLabel").pack(side="left", padx=(0, 4)); widget.pack(side="left", padx=(0, 10))
        self._button(filters, "Refresh", self.refresh_status).pack(side="left")
        actions = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); actions.grid(row=2, column=0, sticky="ew")
        self._button(actions, "Check All Now", self.check_all).pack(side="left")
        self._button(actions, "Check Selected", self.check_selected).pack(side="left", padx=5)
        self._button(actions, "Stop Checking", self.stop_checking, danger=True).pack(side="left")
        ttk.Label(actions, text="Multi-select: Ctrl/Shift + click", style="FingerMonitoringMuted.TLabel").pack(side="left", padx=8)
        self.check_progress = ttk.Progressbar(actions, mode="determinate", maximum=100, length=140, style="FingerMonitoring.Horizontal.TProgressbar")
        self.check_progress.pack(side="left", padx=(8, 4))
        self.progress_percent_var = tk.StringVar(value="0%")
        ttk.Label(actions, textvariable=self.progress_percent_var, style="FingerMonitoringProgress.TLabel", width=5).pack(side="left")
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(actions, textvariable=self.progress_var, style="FingerMonitoringMuted.TLabel").pack(side="right")
        columns = ("unit", "three_lc", "branch", "ip", "model", "status", "note", "online", "days")
        self.status_tree = self._tree(tab, columns, (("unit", "Unit", 85), ("three_lc", "3LC", 85), ("branch", "Branch", 170), ("ip", "IP Address", 125), ("model", "Model", 85), ("status", "Status", 160), ("note", "Note", 220), ("online", "Last Online", 160), ("days", "Offline Days", 95)), row=3)
        self._configure_status_tags(self.status_tree)
        TreeviewCopyHelper(self.status_tree)

    def _build_master(self):
        tab = self.master_tab; tab.columnconfigure(0, weight=1); tab.rowconfigure(2, weight=1)
        filters = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); filters.grid(row=0, column=0, sticky="ew")
        self.master_search = tk.StringVar(); self.master_model = tk.StringVar(value="ALL"); self.master_active = tk.StringVar(value="Active")
        for label, widget in (("Search", ttk.Entry(filters, textvariable=self.master_search, width=23, style="FingerMonitoring.TEntry")), ("Model", ttk.Entry(filters, textvariable=self.master_model, width=16, style="FingerMonitoring.TEntry")), ("Status", ttk.Combobox(filters, textvariable=self.master_active, values=("Active", "Inactive", "All"), state="readonly", width=10, style="FingerMonitoring.TCombobox"))):
            ttk.Label(filters, text=label, style="FingerMonitoringBody.TLabel").pack(side="left", padx=(0, 4)); widget.pack(side="left", padx=(0, 10))
        self._button(filters, "Refresh", self.refresh_master).pack(side="left")
        actions = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); actions.grid(row=1, column=0, sticky="ew", pady=7)
        for text, command in (("Add", self.add_device), ("Edit", self.edit_device), ("Soft Delete", self.delete_device), ("Reactivate", self.reactivate_device), ("Import Excel", self.import_excel), ("Template", self.template_excel), ("Export", self.export_excel)):
            self._button(actions, text, command, danger=text == "Soft Delete").pack(side="left", padx=(0, 4))
        ttk.Label(actions, text="Multi-select: Ctrl/Shift + click", style="FingerMonitoringMuted.TLabel").pack(side="right")
        self.master_tree = self._tree(tab, ("unit", "three_lc", "branch", "ip", "model", "active", "note"), (("unit", "Unit", 85), ("three_lc", "3LC", 85), ("branch", "Branch", 180), ("ip", "IP Address", 130), ("model", "Model", 90), ("active", "Active", 80), ("note", "Note", 260)), row=2)
        TreeviewCopyHelper(self.master_tree)

    def _build_history(self):
        tab = self.history_tab; tab.columnconfigure(0, weight=1); tab.rowconfigure(1, weight=1)
        filters = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); filters.grid(row=0, column=0, sticky="ew")
        self.history_from = tk.StringVar(); self.history_to = tk.StringVar(); self.history_branch = tk.StringVar(); self.history_status = tk.StringVar()
        self.history_from_entry = DateEntry(filters, textvariable=self.history_from, width=10)
        self.history_to_entry = DateEntry(filters, textvariable=self.history_to, width=10)
        for label, widget in (("From", self.history_from_entry), ("To", self.history_to_entry), ("Branch", ttk.Entry(filters, textvariable=self.history_branch, width=18, style="FingerMonitoring.TEntry")), ("Status", ttk.Combobox(filters, textvariable=self.history_status, values=("", "ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR"), width=19, style="FingerMonitoring.TCombobox"))):
            ttk.Label(filters, text=label, style="FingerMonitoringBody.TLabel").pack(side="left", padx=(0, 3)); widget.pack(side="left", padx=(0, 8))
        self._button(filters, "Refresh", self.refresh_history).pack(side="left")
        self._button(filters, "Export Excel", self.export_history).pack(side="left", padx=4)
        self.history_tree = self._tree(tab, ("time", "unit", "three_lc", "branch", "ip", "model", "status", "latency", "detail"), (("time", "Checked", 155), ("unit", "Unit", 85), ("three_lc", "3LC", 85), ("branch", "Branch", 150), ("ip", "IP", 120), ("model", "Model", 75), ("status", "Status", 155), ("latency", "Latency", 75), ("detail", "Diagnostic", 260)), row=1)
        self._set_sort_heading(self.history_tree, "time", True)
        self._configure_status_tags(self.history_tree)
        TreeviewCopyHelper(self.history_tree)
        self.pagination = PaginationBar(tab, self.history_previous, self.history_next); self.pagination.grid(row=2, column=0, sticky="e", pady=(7, 0))

    def _build_backup(self):
        tab = self.backup_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        form = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame")
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        self.backup_root_var = tk.StringVar()
        self.backup_reference_var = tk.StringVar()
        self.backup_exclusions_var = tk.StringVar(value="arsip*;archive*")
        ttk.Label(form, text="Folder Sharing", style="FingerMonitoringBody.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=3)
        ttk.Entry(form, textvariable=self.backup_root_var, style="FingerMonitoring.TEntry").grid(row=0, column=1, sticky="ew", pady=3)
        self._button(form, "Pilih Folder", self.choose_backup_root).grid(row=0, column=2, padx=5, pady=3)
        ttk.Label(form, text="Tanggal Acuan", style="FingerMonitoringBody.TLabel").grid(row=0, column=3, sticky="w", padx=(12, 5), pady=3)
        self.backup_reference_entry = DateEntry(form, textvariable=self.backup_reference_var, width=11)
        self.backup_reference_entry.grid(row=0, column=4, sticky="w", pady=3)
        self.backup_reference_entry.set_iso(date.today().isoformat())

        ttk.Label(form, text="Pengecualian Arsip", style="FingerMonitoringBody.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=3)
        ttk.Entry(form, textvariable=self.backup_exclusions_var, style="FingerMonitoring.TEntry").grid(row=1, column=1, sticky="ew", pady=3)
        self.backup_save_button = self._button(
            form,
            "Simpan Pengaturan",
            self.save_backup_settings,
        )
        self.backup_save_button.grid(row=1, column=4, sticky="w", pady=3)
        self.backup_settings_status_var = tk.StringVar(value="Pengaturan akan dimuat otomatis.")
        ttk.Label(form, textvariable=self.backup_settings_status_var, style="FingerMonitoringMuted.TLabel").grid(row=2, column=1, columnspan=4, sticky="w", pady=(2, 0))

        actions = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame")
        actions.grid(row=1, column=0, sticky="ew", pady=7)
        self.backup_check_button = self._button(actions, "Cek Backup", self.check_backup)
        self.backup_check_button.pack(side="left")
        self.backup_export_button = self._button(actions, "Export Excel", self.export_backup)
        self.backup_export_button.pack(side="left", padx=5)
        self.backup_export_button.configure(state="disabled")
        self.backup_email_button = self._button(actions, "Kirim Email", self.send_backup_email)
        self.backup_email_button.pack(side="left")
        self.backup_email_button.configure(state="disabled")
        self.backup_progress = ttk.Progressbar(actions, mode="determinate", maximum=100, length=180, style="FingerMonitoring.Horizontal.TProgressbar")
        self.backup_progress.pack(side="left", padx=(14, 5))
        self.backup_progress_var = tk.StringVar(value="Belum diperiksa")
        ttk.Label(actions, textvariable=self.backup_progress_var, style="FingerMonitoringMuted.TLabel").pack(side="left")
        self.backup_summary_var = tk.StringVar(value="Hasil pemeriksaan akan tampil setelah Cek Backup.")
        ttk.Label(tab, textvariable=self.backup_summary_var, style="FingerMonitoringBody.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 7))
        columns = ("unit", "branch", "file", "modified", "size", "status", "detail")
        specs = (("unit", "Unit", 90), ("branch", "Cabang", 105), ("file", "File", 220), ("modified", "Modified", 155), ("size", "Ukuran", 100), ("status", "Status", 160), ("detail", "Keterangan", 360))
        self.backup_tree = self._tree(tab, columns, specs, row=3)
        for status, color in (("Memenuhi", palette.teal_pressed), ("Kedaluwarsa", "#9A6700"), ("File wajib hilang", "#B3261E"), ("Gagal diakses", "#B3261E")):
            self.backup_tree.tag_configure(status, foreground=color)
        TreeviewCopyHelper(self.backup_tree)

    def _tree(self, parent, columns, specs, *, row):
        body = ttk.Frame(parent, style="FingerMonitoringCard.TFrame", padding=5); body.grid(row=row, column=0, sticky="nsew"); parent.rowconfigure(row, weight=1); body.columnconfigure(0, weight=1); body.rowconfigure(0, weight=1)
        tree = ttk.Treeview(body, columns=columns, show="headings", style="FingerMonitoring.Treeview", selectmode="extended")
        self._tree_sort_state[tree] = (None, False)
        self._tree_heading_labels[tree] = {
            key: heading for key, heading, _ in specs
        }
        for key, heading, width in specs:
            tree.heading(
                key,
                text=heading,
                command=lambda column=key, target=tree: self._sort_by_column(
                    target, column
                ),
            )
            tree.column(key, width=width, stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical_bar = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        vertical_bar.grid(row=0, column=1, sticky="ns")
        horizontal_bar = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
        horizontal_bar.grid(row=1, column=0, sticky="ew")
        tree.configure(
            yscrollcommand=vertical_bar.set,
            xscrollcommand=horizontal_bar.set,
        )
        return tree

    def on_show(self):
        self._load_backup_settings(); self.refresh_all(); self._poll_events(); self._start_online_blink()

    def on_hide(self):
        if self._event_job: self.after_cancel(self._event_job); self._event_job = None
        if self._online_blink_job:
            self.after_cancel(self._online_blink_job)
            self._online_blink_job = None

    def dispose(self): self.on_hide()

    def refresh_all(self):
        self.refresh_status(); self.refresh_master(); self.refresh_history()

    def _load_backup_settings(self):
        if self._backup_settings_requested:
            return
        self._backup_settings_requested = True
        self.backup_settings_status_var.set("Memuat pengaturan Backup MDB...")

        def done(settings):
            self.backup_root_var.set(settings["root"])
            self.backup_exclusions_var.set(settings["exclusions"])
            self.backup_settings_status_var.set("Pengaturan Backup MDB sudah dimuat.")

        self._background(
            self.service.backup_monitoring_settings,
            done,
            refresh_key="backup_settings",
        )

    def save_backup_settings(self):
        root = self.backup_root_var.get().strip()
        exclusions_text = self.backup_exclusions_var.get().strip()
        self.service.backup_monitoring.parse_archive_exclusions(exclusions_text)

        self.backup_save_button.configure(state="disabled")
        self.backup_settings_status_var.set("Menyimpan pengaturan Backup MDB...")

        def complete(result):
            self.backup_save_button.configure(state="normal")
            if result.success:
                self.backup_settings_status_var.set("Pengaturan Backup MDB tersimpan.")
                return
            self.backup_settings_status_var.set("Pengaturan Backup MDB gagal disimpan.")
            self.services.dialog_service.error(
                "Monitoring Backup MDB",
                result.error or "Pengaturan gagal disimpan.",
            )

        self.services.task_runner.submit(
            lambda: self.service.save_backup_monitoring_settings(
                root, exclusions_text
            ),
            on_done=complete,
        )

    def _background(self, work, done, *, refresh_key=None):
        if refresh_key is not None:
            if refresh_key in self._refresh_inflight:
                self._refresh_latest[refresh_key] = (work, done)
                return
            self._refresh_inflight.add(refresh_key)

        def complete(result):
            if refresh_key is not None:
                latest = self._refresh_latest.pop(refresh_key, None)
                self._refresh_inflight.discard(refresh_key)
                if latest is not None:
                    self._background(*latest, refresh_key=refresh_key)
                    return
            if result.success: done(result.value)
            else: self.services.dialog_service.error("Finger Monitoring", result.error or "Operation failed")
        self.services.task_runner.submit(work, on_done=complete)

    def refresh_status(self):
        search, model, state = self.status_search.get(), self.status_model.get(), self.status_filter.get()
        def done(value):
            dashboard, rows = value
            for key, name in (("Total", "total"), ("Online", "online"), ("Offline", "offline"), ("Alert ≥3 Days", "alert")): self.kpi_vars[key].set(str(dashboard[name]))
            self._status_rows = tuple(rows)
            self._render_status_rows()
        self._background(lambda: self.service.status_snapshot(search=search, device_model=None if model == "ALL" else model, status=state), done, refresh_key="status")

    @staticmethod
    def _status_display(status):
        if status == "ONLINE":
            return "🟢 ONLINE"
        indicators = {
            "ONLINE": "●",
            "OFFLINE": "●",
            "NETWORK_UNREACHABLE": "●",
            "UNKNOWN": "●",
            "ERROR": "●",
        }
        return f"{indicators.get(status, '○')} {status.replace('_', ' ')}"

    @staticmethod
    def _configure_status_tags(tree, *, color_online=True):
        for status, color in (
            ("ONLINE", palette.teal_pressed),
            ("OFFLINE", "#B3261E"),
            ("NETWORK_UNREACHABLE", "#9A6700"),
            ("UNKNOWN", "#9A6700"),
            ("ERROR", "#B3261E"),
        ):
            if status != "ONLINE" or color_online:
                tree.tag_configure(status, foreground=color)

    def _start_online_blink(self):
        if self._online_blink_job is None:
            self._blink_online_status()

    def _blink_online_status(self):
        """Pulse only the ONLINE status marker without refreshing monitoring data."""

        self._online_blink_is_dim = not self._online_blink_is_dim
        marker = "🟢" if self._online_blink_is_dim else "🟩"
        for item_id in self.status_tree.get_children():
            if "ONLINE" not in self.status_tree.item(item_id, "tags"):
                continue
            values = list(self.status_tree.item(item_id, "values"))
            values[5] = f"{marker} ONLINE"
            self.status_tree.item(item_id, values=values)
        self._online_blink_job = self.after(
            self.online_blink_interval_ms,
            self._blink_online_status,
        )

    def refresh_master(self):
        search, model = self.master_search.get(), self.master_model.get()
        active = {"Active": True, "Inactive": False, "All": None}[self.master_active.get()]
        self._background(
            lambda: self.service.device_master.search(
                search=search,
                device_model=None if model == "ALL" else model,
                active=active,
            ),
            self._set_master_rows,
            refresh_key="master",
        )

    def refresh_history(self):
        date_from, date_to = self._history_dates()
        if date_from is None:
            return
        branch, status, offset = self.history_branch.get(), self.history_status.get(), self.history_offset
        self._background(
            lambda: self.service.history(
                date_from=date_from,
                date_to=date_to,
                branch=branch,
                status=status,
                limit=self.history_page_size,
                offset=offset,
                sort_by=self._history_sort_by,
                descending=self._history_sort_descending,
            ),
            self._render_history,
            refresh_key="history",
        )

    def choose_backup_root(self):
        path = self.services.dialog_service.select_folder(
            title="Pilih Folder Sharing Utama Backup MDB"
        )
        if path:
            self.backup_root_var.set(str(path))

    def check_backup(self):
        try:
            root_text = self.backup_root_var.get().strip()
            if not root_text:
                raise ValueError("Pilih folder sharing utama terlebih dahulu.")
            root = Path(root_text)
            reference_text = self.backup_reference_entry.get_iso()
            if reference_text is None:
                raise ValueError("Tanggal acuan wajib diisi.")
            reference_date = date.fromisoformat(reference_text)
            exclusions_text = self.backup_exclusions_var.get().strip()
            exclusions = self.service.backup_monitoring.parse_archive_exclusions(
                exclusions_text
            )
        except (TypeError, ValueError) as exc:
            self.services.dialog_service.warning("Monitoring Backup MDB", str(exc))
            return

        self._backup_snapshot = None
        self._backup_rows = ()
        self._render_backup_rows()
        self.backup_check_button.configure(state="disabled")
        self.backup_export_button.configure(state="disabled")
        self.backup_email_button.configure(state="disabled")
        self.backup_progress["value"] = 0
        self.backup_progress_var.set("Memulai pemeriksaan...")
        self.backup_summary_var.set("Memindai file MDB dari folder sharing...")
        self._backup_progress_queue = queue.SimpleQueue()

        def progress(current, total, message):
            self._backup_progress_queue.put((current, total, message))

        def work():
            self.service.save_backup_monitoring_settings(
                root_text,
                exclusions_text,
            )
            return self.service.backup_monitoring.scan(
                root,
                reference_date,
                archive_exclusions=exclusions,
                progress_callback=progress,
            )

        def complete(result):
            self.backup_check_button.configure(state="normal")
            if not result.success:
                self.backup_progress_var.set("Pemeriksaan gagal")
                self.backup_summary_var.set(result.error or "Pemeriksaan gagal.")
                self.services.dialog_service.error(
                    "Monitoring Backup MDB", result.error or "Pemeriksaan gagal."
                )
                return
            self.backup_settings_status_var.set("Pengaturan Backup MDB tersimpan.")
            snapshot = result.value
            self._backup_snapshot = snapshot
            self._backup_rows = tuple({
                "unit": row.unit,
                "branch": row.branch,
                "file_name": row.file_name,
                "modified_at": row.modified_at.isoformat(sep=" ") if row.modified_at else "",
                "size_bytes": row.size_bytes,
                "status": row.status,
                "detail": row.detail,
            } for row in snapshot.files)
            self._render_backup_rows()
            problems = len(snapshot.problem_files)
            self.backup_progress["value"] = 100
            self.backup_progress_var.set("100% - selesai")
            self.backup_summary_var.set(
                f"{len(snapshot.files)} hasil | {len(snapshot.branches)} cabang | "
                f"{problems} bermasalah | Batas H-3: {snapshot.cutoff_date.isoformat()}"
            )
            self.backup_export_button.configure(state="normal")
            self.backup_email_button.configure(
                state="normal" if problems else "disabled"
            )

        self.services.task_runner.submit(work, on_done=complete)

    def _drain_backup_progress(self):
        latest = None
        while True:
            try:
                latest = self._backup_progress_queue.get_nowait()
            except queue.Empty:
                break
        if latest is None:
            return
        current, total, message = latest
        percent = min(100, round(current * 100 / total)) if total else 0
        self.backup_progress["value"] = percent
        self.backup_progress_var.set(
            f"{percent}% ({current}/{total}) - {message}" if total else message
        )

    def _render_backup_rows(self):
        rows = self._sorted_rows(
            self.backup_tree,
            self._backup_rows,
            {
                "unit": "unit", "branch": "branch", "file": "file_name",
                "modified": "modified_at", "size": "size_bytes",
                "status": "status", "detail": "detail",
            },
        )
        self._fill(
            self.backup_tree,
            rows,
            lambda row: (
                row["unit"], row["branch"], row["file_name"],
                row["modified_at"] or "—",
                f"{row['size_bytes']:,}" if row["size_bytes"] is not None else "—",
                row["status"], row["detail"],
            ),
        )

    def export_backup(self):
        if self._backup_snapshot is None:
            return
        path = self.services.dialog_service.save_file(
            title="Export Monitoring Backup MDB",
            default_name=(
                f"Monitoring_Backup_MDB_{self._backup_snapshot.reference_date.isoformat()}.xlsx"
            ),
            filetypes=(("Excel", "*.xlsx"),),
        )
        if path:
            snapshot = self._backup_snapshot
            self._background(
                lambda: self.service.backup_monitoring.export(snapshot, path),
                lambda value: self.services.dialog_service.info(
                    "Monitoring Backup MDB", f"Export selesai:\n{value}"
                ),
            )

    def send_backup_email(self):
        snapshot = self._backup_snapshot
        if snapshot is None or not snapshot.problem_files:
            self.services.dialog_service.info(
                "Monitoring Backup MDB", "Tidak ada file bermasalah untuk dikirim."
            )
            return
        if not self.services.dialog_service.confirm(
            "Kirim Email Monitoring Backup MDB",
            f"Kirim {len(snapshot.problem_files)} file bermasalah melalui Outlook Classic?",
        ):
            return
        recipient = str(self.service.settings()["recipient_email"])
        self._background(
            lambda: self.service.backup_monitoring.send_email(snapshot, recipient),
            lambda sent: self.services.dialog_service.info(
                "Monitoring Backup MDB",
                "Email berhasil dikirim." if sent else "Tidak ada masalah untuk dikirim.",
            ),
        )

    def _render_history(self, value):
        self._fill(self.history_tree, value["items"], lambda r: (r["checked_at"], r["unit"], r["three_lc"], r["branch_name"], r["ip_address"], r["device_model"], self._status_display(r["status"]), r["latency_ms"] if r["latency_ms"] is not None else "—", r["diagnostic"] or ""), ids=True)
        self.pagination.update_state(offset=self.history_offset, limit=self.history_page_size, total=value["total"])

    def _set_master_rows(self, rows):
        self._master_rows = tuple(rows)
        self._render_master_rows()

    def _render_status_rows(self):
        rows = self._sorted_rows(
            self.status_tree,
            self._status_rows,
            {
                "unit": "unit", "three_lc": "three_lc", "branch": "branch_name", "ip": "ip_address", "model": "device_model", "note": "note",
                "status": "status", "online": "last_online", "days": "offline_days",
            },
        )
        self._fill(
            self.status_tree,
            rows,
            lambda r: (
                r["unit"], r["three_lc"], r["branch_name"], r["ip_address"], r["device_model"],
                self._status_display(r["status"]), r["note"], r["last_online"] or "—", r["offline_days"],
            ),
            ids=True,
        )

    def _render_master_rows(self):
        rows = self._sorted_rows(
            self.master_tree,
            self._master_rows,
            {"unit": "unit", "three_lc": "three_lc", "branch": "branch_name", "ip": "ip_address", "model": "device_model", "note": "note", "active": "is_active"},
        )
        self._fill(
            self.master_tree,
            rows,
            lambda r: (
                r["unit"], r["three_lc"], r["branch_name"], r["ip_address"], r["device_model"],
                "YES" if r["is_active"] else "NO", r["note"],
            ),
            ids=True,
        )

    def _sort_by_column(self, tree, column):
        history_columns = {
            "time": "checked_at", "unit": "unit", "three_lc": "three_lc", "branch": "branch_name", "ip": "ip_address",
            "model": "device_model", "status": "status", "latency": "latency_ms",
            "detail": "diagnostic",
        }
        if tree is self.history_tree:
            sort_by = history_columns[column]
            if self._history_sort_by == sort_by:
                self._history_sort_descending = not self._history_sort_descending
            else:
                self._history_sort_by = sort_by
                self._history_sort_descending = False
            self.history_offset = 0
            self._set_sort_heading(tree, column, self._history_sort_descending)
            self.refresh_history()
            return

        current, descending = self._tree_sort_state[tree]
        descending = not descending if current == column else False
        self._tree_sort_state[tree] = (column, descending)
        self._set_sort_heading(tree, column, descending)
        if tree is self.status_tree:
            self._render_status_rows()
        elif tree is self.backup_tree:
            self._render_backup_rows()
        else:
            self._render_master_rows()

    def _set_sort_heading(self, tree, selected, descending):
        for column, label in self._tree_heading_labels[tree].items():
            suffix = " ↓" if column == selected and descending else " ↑" if column == selected else ""
            tree.heading(column, text=label + suffix)

    def _sorted_rows(self, tree, rows, columns):
        column, descending = self._tree_sort_state[tree]
        if not column:
            return rows
        key = columns[column]
        populated = [row for row in rows if row.get(key) not in (None, "")]
        missing = [row for row in rows if row.get(key) in (None, "")]

        def sort_key(row):
            value = row[key]
            if key == "ip_address":
                return ipaddress.ip_address(value)
            if key in {"offline_days", "latency_ms", "is_active", "size_bytes"}:
                return int(value)
            return str(value).casefold()

        return tuple(sorted(populated, key=sort_key, reverse=descending) + missing)

    @staticmethod
    def _fill(tree, rows, values, *, ids=False):
        tree.delete(*tree.get_children())
        for row in rows:
            tag = row.get("status", "")
            tree.insert("", "end", iid=str(row["device_id"] if ids and "device_id" in row else row.get("result_id", "")) or None, values=values(row), tags=(tag,) if tag else ())

    def check_all(self): self._check(self.service.check_all, "Check All dimulai.")
    def check_selected(self): self._check(lambda: self.service.check_selected(self._selected_ids(self.status_tree)), "Check Selected dimulai.")
    def _check(self, action, message):
        if action(): self.progress_var.set(message)
        else: self.progress_var.set("Monitoring belum siap atau cycle masih berjalan.")
    def stop_checking(self): self.progress_var.set("Membatalkan cycle..." if self.service.cancel_current_cycle() else "Tidak ada cycle aktif.")
    @staticmethod
    def _selected_ids(tree): return tuple(int(item) for item in tree.selection())

    def _selected_master(self):
        selection = self.master_tree.selection(); return int(selection[0]) if selection else None
    def add_device(self): self._device_dialog()
    def edit_device(self):
        selected = self._selected_master()
        if selected is None: return self.services.dialog_service.warning("Device Master", "Pilih perangkat.")
        item = self.master_tree.item(str(selected), "values"); self._device_dialog(selected, item)
    def _device_dialog(self, device_id=None, values=()):
        window = tk.Toplevel(self); window.title("Add Device" if device_id is None else "Edit Device"); window.transient(self.winfo_toplevel())
        unit, three_lc, branch, ip, model, note = (
            tk.StringVar(value=values[0] if values else ""),
            tk.StringVar(value=values[1] if values else ""),
            tk.StringVar(value=values[2] if values else ""),
            tk.StringVar(value=values[3] if values else ""),
            tk.StringVar(value=values[4] if values else "X1500"),
            tk.StringVar(value=values[5] if values else ""),
        )
        for row, (label, variable) in enumerate((("Unit", unit), ("3LC", three_lc), ("Branch Name *", branch), ("IP Address *", ip), ("Model", model), ("Note", note))):
            ttk.Label(window, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w"); ttk.Entry(window, textvariable=variable, style="FingerMonitoring.TEntry").grid(row=row, column=1, padx=10, pady=6)
        def save():
            try:
                if device_id is None: self.service.device_master.add_device(branch.get(), ip.get(), device_model=model.get(), unit=unit.get(), three_lc=three_lc.get(), note=note.get())
                else: self.service.device_master.edit_device(device_id, branch.get(), ip.get(), device_model=model.get(), unit=unit.get(), three_lc=three_lc.get(), note=note.get())
            except Exception as exc: return self.services.dialog_service.error("Device Master", str(exc))
            window.destroy(); self.refresh_master(); self.refresh_status()
        self._button(window, "Save", save).grid(row=6, column=1, padx=10, pady=10, sticky="e")
    def delete_device(self):
        selected = self._selected_master()
        if selected and self.services.dialog_service.confirm("Soft Delete", "Nonaktifkan perangkat ini?"):
            self.service.device_master.soft_delete(selected); self.refresh_master(); self.refresh_status()
    def reactivate_device(self):
        selected = self._selected_master()
        if selected:
            try: self.service.device_master.reactivate(selected)
            except Exception as exc: self.services.dialog_service.error("Reactivate", str(exc))
            self.refresh_master(); self.refresh_status()
    def import_excel(self):
        path = self.services.dialog_service.select_file(title="Import Device Master", filetypes=(("Excel", "*.xlsx"),))
        if not path: return
        self._background(lambda: self.service.device_master.preview_import(path), self._confirm_import)
    def _confirm_import(self, preview):
        text = f"Insert: {preview.insert_count}\nUpdate: {preview.update_count}\nRejected: {preview.rejected_count}"
        if preview.can_commit and self.services.dialog_service.confirm("Import Preview", text + "\n\nTerapkan import?"):
            self._background(lambda: self.service.device_master.commit_import(preview), lambda _: (self.refresh_master(), self.refresh_status()))
        elif not preview.can_commit: self.services.dialog_service.warning("Import Preview", text + "\nPerbaiki file sebelum import.")
    def template_excel(self):
        path = self.services.dialog_service.save_file(title="Save Template", default_name="OASK_Finger_Device_Master_Template.xlsx", filetypes=(("Excel", "*.xlsx"),))
        if path: self._background(lambda: self.service.device_master.generate_template(path), lambda value: self.services.dialog_service.info("Template", f"Template dibuat:\n{value}"))
    def export_excel(self):
        path = self.services.dialog_service.save_file(title="Export Device Master", default_name="Finger_Device_Master.xlsx", filetypes=(("Excel", "*.xlsx"),))
        if path:
            search, model = self.master_search.get(), self.master_model.get()
            active = {"Active":True,"Inactive":False,"All":None}[self.master_active.get()]
            self._background(lambda: self.service.device_master.export(path, search=search, device_model=None if model=="ALL" else model, active=active), lambda value: self.services.dialog_service.info("Export", f"Export selesai:\n{value}"))
    def export_history(self):
        path = self.services.dialog_service.save_file(title="Export Finger Monitoring History", default_name="Finger_Monitoring_History.xlsx", filetypes=(("Excel", "*.xlsx"),))
        if path:
            date_from, date_to = self._history_dates()
            if date_from is None:
                return
            branch, status = self.history_branch.get(), self.history_status.get()
            self._background(lambda: self.service.export_history(path, date_from=date_from, date_to=date_to, branch=branch, status=status, sort_by=self._history_sort_by, descending=self._history_sort_descending), lambda value: self.services.dialog_service.info("Export", f"Export selesai:\n{value}"))
    def _history_dates(self):
        try:
            return self.history_from_entry.get_iso() or "", self.history_to_entry.get_iso() or ""
        except ValueError as exc:
            self.services.dialog_service.warning("History", str(exc))
            return None, None
    def history_previous(self): self.history_offset=max(0,self.history_offset-self.history_page_size); self.refresh_history()
    def history_next(self): self.history_offset+=self.history_page_size; self.refresh_history()
    def _poll_events(self):
        self._drain_backup_progress()
        events = self.service.drain_events()
        if events:
            latest = events[-1]; self.progress_var.set(latest.name.replace("_", " "))
            for event in events:
                if event.name == "CYCLE_STARTED":
                    self._cycle_total = int(event.payload.get("requested_devices", 0)); self._cycle_checked = 0; self.check_progress["value"] = 0; self.progress_percent_var.set("0%")
                elif event.name == "DEVICE_RESULT":
                    self._cycle_checked += 1
                    if self._cycle_total:
                        percent = min(100, round(self._cycle_checked * 100 / self._cycle_total))
                        self.check_progress["value"] = percent
                        self.progress_percent_var.set(f"{percent}%")
                    self.progress_var.set(f"Checked {self._cycle_checked}/{self._cycle_total}")
                elif event.name == "CYCLE_FINISHED":
                    percent = min(100, round(self._cycle_checked * 100 / self._cycle_total)) if self._cycle_total else 0
                    self.check_progress["value"] = percent
                    self.progress_percent_var.set(f"{percent}%")
            if any(event.name in {"DEVICE_RESULT", "CYCLE_FINISHED"} for event in events): self.refresh_status(); self.refresh_history()
        else:
            state = self.service.coordinator_status()
            if state.get("running") and not state.get("cycle_active") and state.get("next_delay_seconds"):
                self.progress_var.set(f"Next automatic check in {max(0, int(state['next_delay_seconds'] // 60))} minutes")
        self._event_job = self.after(500, self._poll_events)
