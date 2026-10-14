"""Finger Monitoring settings and non-destructive maintenance status."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.pages.settings.common import SettingsSection


class FingerMonitoringSection(SettingsSection):
    def __init__(self, parent, page):
        super().__init__(parent, page)
        self.variables = {
            "recipient_email": tk.StringVar(), "daily_report_start": tk.StringVar(),
            "auto_check_interval_hours": tk.StringVar(), "ping_timeout_ms": tk.StringVar(),
            "max_workers": tk.StringVar(), "offline_alert_observed_dates": tk.StringVar(),
        }
        card = ttk.Frame(self, style="ContentCard.TFrame", padding=14); card.grid(row=0, column=0, sticky="ew")
        fields = (("Recipient Email", "recipient_email"), ("Daily Report Start", "daily_report_start"), ("Auto Check Interval (hours)", "auto_check_interval_hours"), ("Ping Timeout (ms)", "ping_timeout_ms"), ("Max Workers", "max_workers"), ("Offline Alert (dates)", "offline_alert_observed_dates"))
        for row, (label, key) in enumerate(fields):
            ttk.Label(card, text=label, style="CardText.TLabel").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(card, textvariable=self.variables[key], width=32).grid(row=row, column=1, sticky="w", padx=10, pady=3)
        self.action_button(text="Save Finger Monitoring Settings", command=self.save, row=1)
        self.status_var = tk.StringVar(value="Database belum diperiksa.")
        ttk.Label(self, text="Database Maintenance", style="SectionHeader.TLabel").grid(row=2, column=0, sticky="w", pady=(16, 4))
        maintenance = ttk.Frame(self, style="ContentCard.TFrame", padding=12); maintenance.grid(row=3, column=0, sticky="ew")
        ttk.Label(maintenance, textvariable=self.status_var, style="CardText.TLabel").pack(anchor="w")
        self.email_var = tk.StringVar(value="Last email: -")
        ttk.Label(maintenance, textvariable=self.email_var, style="CardText.TLabel").pack(anchor="w", pady=(4, 0))
        self.action_button(text="Create / Initialize Database", command=self.initialize, row=4)
        cleanup = ttk.Frame(self, style="OASK.TFrame"); cleanup.grid(row=5, column=0, sticky="w", pady=2)
        self.retention_var = tk.StringVar(value="90")
        ttk.Combobox(cleanup, textvariable=self.retention_var, values=("30", "90", "180", "All"), state="readonly", width=8).pack(side="left", padx=(0, 6))
        cleanup_button = ttk.Button(cleanup, text="Cleanup History", command=self.cleanup, style="Secondary.TButton"); cleanup_button.pack(side="left")
        self.page.register_action(cleanup_button)
        self.action_button(text="Reset Monitoring Data", command=self.reset, row=6)
        self.action_button(text="Compact Database", command=self.compact, row=7)
        self.action_button(text="Retry Daily Email", command=self.retry_email, row=8)

    def on_selected(self): self.load()

    def load(self):
        def done(value):
            settings, status, email = value
            for key, variable in self.variables.items(): variable.set(str(settings[key]))
            self.status_var.set(f"{status.status} | {status.database_path or '-'} | {status.size_bytes or 0:,} bytes")
            self.email_var.set("Last email: -" if email is None else f"Last email: {email['report_date']} | {email['status']} | {email['error_detail'] or '-'}")
        self.page.run_task(lambda: (self.services.finger_monitoring_service.settings(), self.services.finger_monitoring_service.storage.resolve_status(), self.services.finger_monitoring_service.latest_email_delivery()), on_success=done, message="Memuat Finger Monitoring Settings...")

    def initialize(self):
        self.page.run_task(self.services.finger_monitoring_service.initialize, on_success=lambda status: self.status_var.set(f"{status.status} | {status.database_path} | {status.size_bytes or 0:,} bytes"), message="Inisialisasi Finger Monitoring...")

    def save(self):
        try:
            values = {key: (int(var.get()) if key in {"auto_check_interval_hours", "ping_timeout_ms", "max_workers", "offline_alert_observed_dates"} else var.get()) for key, var in self.variables.items()}
        except ValueError:
            return self.services.dialog_service.warning("Finger Monitoring", "Nilai angka tidak valid.")
        self.page.run_task(lambda: self.services.finger_monitoring_service.save_settings(**values), on_success=lambda _: self.services.dialog_service.info("Finger Monitoring", "Settings tersimpan. Max workers berlaku saat coordinator berikutnya dimulai."), message="Menyimpan Finger Monitoring Settings...")

    def cleanup(self):
        days = None if self.retention_var.get() == "All" else int(self.retention_var.get())
        def show(preview):
            message = f"Delete results: {preview.result_count:,}\nEligible cycles: {preview.cycle_count:,}\nRetention: {preview.retention_days or 'All'}"
            if self.services.dialog_service.confirm("Cleanup History Preview", message + "\n\nContinue?"):
                self.page.run_task(lambda: self.services.finger_monitoring_service.maintenance.cleanup(preview), on_success=lambda result: (self.services.dialog_service.info("Cleanup History", str(result)), self.load()), message="Cleanup Finger Monitoring History...", destructive=True)
        self.page.run_task(lambda: self.services.finger_monitoring_service.maintenance.preview_cleanup(days), on_success=show, message="Preparing Cleanup Preview...")

    def reset(self):
        if not self.services.dialog_service.typed_confirm("Reset Monitoring Data", "Device Master dan Settings dipertahankan. Ketik RESET MONITORING DATA", "RESET MONITORING DATA"):
            return
        self.page.run_task(lambda: self.services.finger_monitoring_service.maintenance.reset_monitoring_data(confirmation="RESET MONITORING DATA"), on_success=lambda result: (self.services.dialog_service.info("Reset Monitoring Data", str(result)), self.load()), message="Reset Monitoring Data...", destructive=True, cancellable=False)

    def compact(self):
        if not self.services.dialog_service.confirm("Compact Database", "Backup tervalidasi akan dibuat sebelum VACUUM. Continue?"):
            return
        self.page.run_task(self.services.finger_monitoring_service.maintenance.compact, on_success=lambda result: (self.services.dialog_service.info("Compact Database", f"Backup: {result['backup_path']}\nSize: {result['size_bytes']:,} bytes"), self.load()), message="Backup dan Compact Database...", destructive=True, cancellable=False)

    def retry_email(self):
        self.page.run_task(self.services.finger_monitoring_service.retry_daily_email, on_success=lambda started: self.services.dialog_service.info("Retry Daily Email", "Retry dimulai." if started else "Tidak ada email gagal yang dapat dikirim ulang."), message="Memulai retry email...")
