"""Three-tab GUI for the isolated Finger Monitoring module."""

from __future__ import annotations

import ipaddress
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.pages.base_page import BasePage
from ui.theme.finger_monitoring import apply_finger_monitoring_styles
from ui.theme.palette import palette
from ui.widgets import DateEntry, PaginationBar, TreeviewCopyHelper


class FingerMonitoringPage(BasePage):
    page_id = "finger_monitoring"
    title = "Finger Monitoring"
    subtitle = "Monitoring perangkat Solution X1500/X1800."
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
        self._history_sort_by = "checked_at"
        self._history_sort_descending = True
        self._cycle_total = 0
        self._cycle_checked = 0
        super().__init__(parent, context)

    def build_content(self):
        self.services = self.context.app_services
        self.service = self.services.finger_monitoring_service
        apply_finger_monitoring_styles(self)
        self.configure(style="FingerMonitoringPage.TFrame")
        self.rowconfigure(0, weight=1); self.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(self, style="FingerMonitoring.TNotebook")
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.status_tab = self._tab("DEVICE STATUS")
        self.master_tab = self._tab("DEVICE MASTER")
        self.history_tab = self._tab("HISTORY")
        self._build_status(); self._build_master(); self._build_history()

    def _tab(self, name):
        frame = ttk.Frame(self.notebook, style="FingerMonitoringSurface.TFrame", padding=10)
        self.notebook.add(frame, text=name)
        return frame

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
            "Save": "FingerMonitoringMint.TButton",
        }
        style = "FingerMonitoringDanger.TButton" if danger else accents.get(text, "FingerMonitoring.TButton")
        return ttk.Button(parent, text=text, command=command, style=style)

    def _build_status(self):
        tab = self.status_tab; tab.columnconfigure(0, weight=1); tab.rowconfigure(3, weight=1)
        kpis = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); kpis.grid(row=0, column=0, sticky="ew")
        self.kpi_vars = {name: tk.StringVar(value="0") for name in ("Total", "Online", "Offline", "Alert ≥3 Days")}
        for index, (name, variable) in enumerate(self.kpi_vars.items()):
            card = ttk.Frame(kpis, style="FingerMonitoringCard.TFrame", padding=9); card.grid(row=0, column=index, sticky="ew", padx=(0, 7))
            ttk.Label(card, text=name, style="FingerMonitoringCard.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style="FingerMonitoringCard.TLabel", font=("Segoe UI", 16, "bold")).pack(anchor="w")
            kpis.columnconfigure(index, weight=1)
        filters = ttk.Frame(tab, style="FingerMonitoringSurface.TFrame"); filters.grid(row=1, column=0, sticky="ew", pady=8)
        self.status_search = tk.StringVar(); self.status_filter = tk.StringVar(value="ALL"); self.status_model = tk.StringVar(value="ALL")
        for label, widget in (("Search", ttk.Entry(filters, textvariable=self.status_search, width=23)), ("Status", ttk.Combobox(filters, textvariable=self.status_filter, values=("ALL", "ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR"), state="readonly", width=21)), ("Model", ttk.Combobox(filters, textvariable=self.status_model, values=("ALL", "X1500", "X1800"), state="readonly", width=10))):
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
        for label, widget in (("Search", ttk.Entry(filters, textvariable=self.master_search, width=23)), ("Model", ttk.Combobox(filters, textvariable=self.master_model, values=("ALL", "X1500", "X1800"), state="readonly", width=10)), ("Status", ttk.Combobox(filters, textvariable=self.master_active, values=("Active", "Inactive", "All"), state="readonly", width=10))):
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
        for label, widget in (("From", self.history_from_entry), ("To", self.history_to_entry), ("Branch", ttk.Entry(filters, textvariable=self.history_branch, width=18)), ("Status", ttk.Combobox(filters, textvariable=self.history_status, values=("", "ONLINE", "OFFLINE", "NETWORK_UNREACHABLE", "UNKNOWN", "ERROR"), width=19))):
            ttk.Label(filters, text=label, style="FingerMonitoringBody.TLabel").pack(side="left", padx=(0, 3)); widget.pack(side="left", padx=(0, 8))
        self._button(filters, "Refresh", self.refresh_history).pack(side="left")
        self._button(filters, "Export Excel", self.export_history).pack(side="left", padx=4)
        self.history_tree = self._tree(tab, ("time", "unit", "three_lc", "branch", "ip", "model", "status", "latency", "detail"), (("time", "Checked", 155), ("unit", "Unit", 85), ("three_lc", "3LC", 85), ("branch", "Branch", 150), ("ip", "IP", 120), ("model", "Model", 75), ("status", "Status", 155), ("latency", "Latency", 75), ("detail", "Diagnostic", 260)), row=1)
        self._set_sort_heading(self.history_tree, "time", True)
        self._configure_status_tags(self.history_tree)
        TreeviewCopyHelper(self.history_tree)
        self.pagination = PaginationBar(tab, self.history_previous, self.history_next); self.pagination.grid(row=2, column=0, sticky="e", pady=(7, 0))

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
        tree.grid(row=0, column=0, sticky="nsew"); bar = ttk.Scrollbar(body, orient="vertical", command=tree.yview); bar.grid(row=0, column=1, sticky="ns"); tree.configure(yscrollcommand=bar.set)
        return tree

    def on_show(self):
        self.refresh_all(); self._poll_events(); self._start_online_blink()

    def on_hide(self):
        if self._event_job: self.after_cancel(self._event_job); self._event_job = None
        if self._online_blink_job:
            self.after_cancel(self._online_blink_job)
            self._online_blink_job = None

    def dispose(self): self.on_hide()

    def refresh_all(self):
        self.refresh_status(); self.refresh_master(); self.refresh_history()

    def _background(self, work, done):
        def complete(result):
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
        self._background(lambda: (self.service.dashboard(), self.service.device_status(search=search, device_model=None if model == "ALL" else model, status=state)), done)

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
            ("OFFLINE", "#FF6F91"),
            ("NETWORK_UNREACHABLE", "#FFD166"),
            ("UNKNOWN", "#9A6700"),
            ("ERROR", "#FF6F91"),
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
            values[3] = f"{marker} ONLINE"
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
            if key in {"offline_days", "latency_ms", "is_active"}:
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
            ttk.Label(window, text=label).grid(row=row, column=0, padx=10, pady=6, sticky="w"); ttk.Entry(window, textvariable=variable).grid(row=row, column=1, padx=10, pady=6)
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
