"""Unified Outlook Revisi page backed by the UI5 service boundary."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui.constants import COMPACT_LOG_BACKGROUND, LOG_FONT, LOG_TEXT
from ui.dialogs.module_configuration_detail import ModuleConfigurationDetailDialog
from ui.icon_manager import IconManager
from ui.outlook_revisi_models import (
    OutlookRevisiCancellationToken,
    OutlookRevisiLogEvent,
    OutlookRevisiProgressEvent,
    OutlookRevisiRunRequest,
)
from ui.pages.base_page import BasePage
from ui.widgets import (
    CompactProgress,
    OptionChip,
    ResultSummary,
    SegmentedChoice,
)


class OutlookRevisiPage(BasePage):
    page_id = "outlook_revisi"
    title = "Outlook Revisi"
    subtitle = "Pengelolaan email, attachment, dan validasi Outlook."
    icon_name = "outlook_revisi.ico"
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self._defaults_loaded = False
        self._busy = False
        self._running = False
        self._disposed = False
        self._resolved = None
        self._cancellation = None
        self._last_result = None
        self._run_icon = None
        self._open_folder_icon = None
        super().__init__(parent, context)
        self.configure(padding=(16, 10))

    def build_content(self) -> None:
        self.services = self.context.app_services
        self.config_var = tk.StringVar()
        self.payroll_period_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.workflow_var = tk.StringVar(value="HO")
        self.global_output_var = tk.BooleanVar(value=True)
        self.global_limit_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=True)
        self.message_limit_var = tk.StringVar(value="25")
        self.outbound_ack_var = tk.BooleanVar(value=False)
        self.manual_fallback_var = tk.BooleanVar(value=False)
        self.advanced_var = tk.BooleanVar(value=False)
        self.validation_status_var = tk.StringVar(value="Belum diperiksa")
        self.output_summary_var = tk.StringVar(value="Output: Belum dikonfigurasi")
        self.active_config_var = tk.StringVar(
            value="Konfigurasi: OAS-K Database â€¢ Belum diperiksa"
        )
        self.mailbox_status_var = tk.StringVar(
            value="Mailbox: Belum divalidasi â€¢ Target: karina.hr.1@oto.co.id / Inbox"
        )

        self.surface = ttk.Frame(self, style="OASK.TFrame")
        self.surface.grid(row=1, column=0, sticky="nsew")
        self.surface.columnconfigure(0, weight=1)
        self.surface.rowconfigure(4, weight=1)

        self._build_configuration_strip()
        self._build_operational_panel()
        self._build_action_row()
        self._build_progress()
        self._build_log()
        self._build_result()
        self._build_advanced()

    def _build_configuration_strip(self) -> None:
        strip = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 8))
        strip.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        strip.columnconfigure(0, weight=1)
        ttk.Label(
            strip, textvariable=self.active_config_var, style="CompactTitle.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            strip, textvariable=self.mailbox_status_var, style="CompactText.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        actions = ttk.Frame(strip, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(
            actions,
            text="Lihat Detail",
            style="Attendance.TButton",
            command=self.show_active_configuration,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Refresh",
            style="Attendance.TButton",
            command=self.refresh_active_configuration,
        ).pack(side="left", padx=(6, 0))

    def _build_operational_panel(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 10))
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=4)
        panel.columnconfigure(1, weight=3)
        panel.columnconfigure(2, weight=3)

        period = ttk.Frame(panel, style="CompactBody.TFrame")
        period.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        period.columnconfigure(0, weight=1)
        ttk.Label(period, text="Payroll Period", style="CompactTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            period,
            text="Periode subject email (MM-YYYY)",
            style="CompactText.TLabel",
        ).grid(
            row=1, column=0, sticky="w", pady=(5, 2)
        )
        self.payroll_period_entry = ttk.Entry(
            period,
            textvariable=self.payroll_period_var,
            state="readonly",
            style="Readonly.TEntry",
        )
        self.payroll_period_entry.grid(row=2, column=0, sticky="ew")
        ttk.Button(
            period,
            text="Ubah di Settings",
            style="Attendance.TButton",
            command=self.return_settings,
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))
        workflow = ttk.Frame(period, style="CompactBody.TFrame")
        workflow.grid(row=4, column=0, sticky="w", pady=(7, 0))
        SegmentedChoice(
            workflow,
            variable=self.workflow_var,
            choices=(("HO", "HO"), ("BRANCH", "BRANCH")),
        ).pack(anchor="w")

        safety = ttk.Frame(panel, style="CompactBody.TFrame")
        safety.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        ttk.Label(safety, text="Mailbox & Safety", style="CompactTitle.TLabel").pack(
            anchor="w"
        )
        OptionChip(
            safety,
            text="Safe Preview / Dry Run",
            variable=self.dry_run_var,
        ).pack(anchor="w", pady=(6, 2))
        ttk.Label(
            safety,
            text="Mode SEND wajib konfirmasi ketik SEND.",
            style="StatusWarning.TLabel",
            wraplength=260,
        ).pack(anchor="w", pady=(4, 2))
        OptionChip(
            safety,
            text="Saya memahami live mode email",
            variable=self.outbound_ack_var,
        ).pack(anchor="w")

        output = ttk.Frame(panel, style="CompactBody.TFrame")
        output.grid(row=0, column=2, sticky="nsew")
        output.columnconfigure(0, weight=1)
        ttk.Label(output, text="Output & Limit", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.global_output_check = OptionChip(
            output,
            text="Gunakan output dari Settings",
            variable=self.global_output_var,
            command=self._apply_global_state,
        )
        self.global_output_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 2))
        self.output_entry = ttk.Entry(output, textvariable=self.output_var, style="Modern.TEntry")
        self.output_entry.grid(row=2, column=0, sticky="ew")
        self.output_browse = ttk.Button(
            output, text="Browse", style="Attendance.TButton", command=self.browse_output
        )
        self.output_browse.grid(row=2, column=1, padx=(6, 0))
        ttk.Label(output, text="Email Limit", style="CompactText.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(7, 2)
        )
        self.global_limit_check = OptionChip(
            output,
            text="Gunakan limit default sistem",
            variable=self.global_limit_var,
            command=self._apply_global_state,
        )
        self.global_limit_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 3))
        self.message_limit_entry = ttk.Entry(
            output,
            textvariable=self.message_limit_var,
            width=8,
            style="LimitReadonly.TEntry",
        )
        self.message_limit_entry.grid(row=5, column=0, sticky="w")

    def _build_action_row(self) -> None:
        row = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 7))
        row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        status = ttk.Frame(row, style="CompactBody.TFrame")
        status.grid(row=0, column=0, sticky="w")
        ttk.Label(status, text="Validasi:", style="CompactText.TLabel").pack(side="left")
        ttk.Label(
            status, textvariable=self.validation_status_var, style="CompactStatus.TLabel"
        ).pack(side="left", padx=(5, 0))
        self.validation_summary = ResultSummary(row, wraplength=700)
        self.validation_summary.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.validation_summary.grid_remove()

        actions = ttk.Frame(row, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.validate_config_button = ttk.Button(
            actions,
            text="Periksa Konfigurasi",
            style="Attendance.TButton",
            command=self.validate_configuration,
        )
        self.validate_config_button.pack(side="left")
        self.validate_mailbox_button = ttk.Button(
            actions,
            text="Periksa Mailbox",
            style="Attendance.TButton",
            command=self.validate_mailbox,
        )
        self.validate_mailbox_button.pack(side="left", padx=(6, 0))
        self.run_button = ttk.Button(
            actions,
            text="Start",
            style="AttendancePrimary.TButton",
            command=self.run_outlook,
        )
        self._run_icon = IconManager(
            self.context.assets_path / "icons" / "png",
            master=self.winfo_toplevel(),
            logger=self.context.logger,
        ).load("start_button_pxl.png", size=(120, 48))
        if self._run_icon is not None:
            self.run_button.configure(
                image=self._run_icon,
                text="",
                compound="center",
                style="AttendanceStartImage.TButton",
            )
        self.run_button.pack(side="left", padx=(8, 0), anchor="n")
        self.cancel_button = ttk.Button(
            actions,
            text="Batal",
            style="AttendanceDanger.TButton",
            command=self.cancel,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=(8, 0), anchor="n")
        self.cancel_button.pack_forget()

    def _build_progress(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 6))
        panel.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.progress_panel = panel
        panel.columnconfigure(0, weight=1)
        self.progress = CompactProgress(panel)
        self.progress.grid(row=0, column=0, sticky="ew")

    def _build_log(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(10, 8))
        panel.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        header = ttk.Frame(panel, style="CompactBody.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Process Log", style="CompactTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        log_actions = ttk.Frame(header, style="CompactBody.TFrame")
        log_actions.grid(row=0, column=1, sticky="e")
        ttk.Button(
            log_actions, text="Buka Log", style="Attendance.TButton", command=self.open_process_log
        ).pack(side="left")
        ttk.Button(
            log_actions, text="Salin", style="Attendance.TButton", command=self.copy_log
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            log_actions, text="Bersihkan", style="Attendance.TButton", command=self.clear_log
        ).pack(side="left", padx=(6, 0))
        self.log_text = tk.Text(
            panel,
            height=5,
            wrap="word",
            state="disabled",
            background=COMPACT_LOG_BACKGROUND,
            foreground=LOG_TEXT,
            insertbackground=LOG_TEXT,
            font=LOG_FONT,
            relief="flat",
            padx=8,
            pady=6,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(5, 0))
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _build_result(self) -> None:
        self.result_panel = ttk.Frame(
            self.surface, style="CompactPanel.TFrame", padding=(10, 8)
        )
        self.result_panel.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.result_panel.columnconfigure(0, weight=1)
        self.result_summary = ResultSummary(self.result_panel, wraplength=720)
        self.result_summary.grid(row=0, column=0, sticky="ew")
        recovery = ttk.Frame(self.result_panel, style="CompactBody.TFrame")
        recovery.grid(row=0, column=1, sticky="e", padx=(10, 0))
        for text, command in (
            ("Buka Output", self.open_output),
            ("Buka Attachment", self.open_attachments),
            ("Buka Log", self.open_process_log),
            ("Retry", self.retry),
        ):
            if self._open_folder_icon is None:
                self._open_folder_icon = IconManager(
                    self.context.assets_path / "icons",
                    master=self.winfo_toplevel(),
                    logger=self.context.logger,
                ).load("open_folder.ico", size=16)
            button = ttk.Button(
                recovery, text=text, style="Attendance.TButton", command=command
            )
            if self._open_folder_icon is not None and text != "Retry":
                button.configure(image=self._open_folder_icon, compound="left")
            button.pack(side="left", padx=(6, 0))
        self.result_panel.grid_remove()

    def _build_advanced(self) -> None:
        section = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(10, 6))
        section.grid(row=6, column=0, sticky="ew")
        section.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            section,
            text="Advanced / Manual Fallback",
            variable=self.advanced_var,
            command=self._toggle_advanced,
        ).grid(row=0, column=0, sticky="w")
        self.fallback_frame = ttk.Frame(section, style="CompactBody.TFrame")
        self.fallback_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.fallback_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            self.fallback_frame,
            text="Gunakan workbook konfigurasi sementara",
            variable=self.manual_fallback_var,
            command=self._toggle_fallback,
        ).grid(row=0, column=0, sticky="w")
        self.fallback_file_frame = ttk.Frame(self.fallback_frame, style="CompactBody.TFrame")
        self.fallback_file_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.fallback_file_frame.columnconfigure(0, weight=1)
        ttk.Entry(self.fallback_file_frame, textvariable=self.config_var).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            self.fallback_file_frame,
            text="Pilih Excel",
            style="Attendance.TButton",
            command=self.browse_configuration,
        ).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(
            self.fallback_file_frame,
            text="Buka Folder",
            style="Attendance.TButton",
            command=self.open_configuration,
        ).grid(row=0, column=2, padx=(6, 0))
        self.fallback_file_frame.grid_remove()
        self.fallback_frame.grid_remove()

    def on_show(self) -> None:
        if not self._defaults_loaded and not self._busy:
            self._load_defaults()

    def _load_defaults(self) -> None:
        self._set_busy(True, "Loading Outlook Revisi defaults...")

        def work():
            service = self.services.outlook_revisi_service
            summary_loader = getattr(service, "load_active_configuration", None)
            return service.load_defaults(), (
                summary_loader() if callable(summary_loader) else None
            )

        def done(result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not result.success:
                self.validation_summary.show_lines(
                    [result.error or "Defaults unavailable"]
                )
                return
            value, summary = result.value
            self._defaults_loaded = True
            if value.global_output_root:
                self.output_var.set(str(value.global_output_root))
            self.payroll_period_var.set(value.payroll_period or "")
            self.global_output_var.set(value.global_output_root is not None)
            self.global_limit_var.set(True)
            if not value.database_available:
                self.global_output_check.configure(state="disabled")
                self.global_limit_check.configure(state="disabled")
                self.validation_summary.show_lines([value.warning])
            elif summary is not None:
                fields = " | ".join(f"{key}: {item}" for key, item in summary.fields)
                self.active_config_var.set(
                    f"Status: {summary.status_label} | Sumber: {summary.source}"
                    + (f" | {fields}" if fields else "")
                    + f" | Terakhir Diperbarui: {summary.last_updated or '-'}"
                )
            self._apply_global_state()

        self.services.task_runner.submit(work, on_done=done)

    def browse_configuration(self) -> None:
        path = self.services.dialog_service.select_file(
            title="Pilih Outlook Revisi Configuration",
            filetypes=(("Excel Workbook", "*.xlsx"),),
        )
        if path:
            self.config_var.set(str(path))
            self.advanced_var.set(True)
            self.manual_fallback_var.set(True)
            self._toggle_advanced()
            self._toggle_fallback()

    def _toggle_advanced(self) -> None:
        if self.advanced_var.get():
            self.fallback_frame.grid()
        else:
            self.fallback_frame.grid_remove()
            self.manual_fallback_var.set(False)
            self._toggle_fallback()

    def _toggle_fallback(self) -> None:
        if self.manual_fallback_var.get():
            self.fallback_file_frame.grid()
        else:
            self.fallback_file_frame.grid_remove()
            self.config_var.set("")

    def refresh_active_configuration(self) -> None:
        if not self._busy:
            self._defaults_loaded = False
            self._load_defaults()

    def show_active_configuration(self) -> None:
        module_service = getattr(self.services, "module_configuration_service", None)
        storage = getattr(self.services, "storage_service", None)
        if module_service is None or storage is None:
            self.return_settings()
            return
        status = storage.resolve_status()
        if not status.database_valid or status.database_path is None:
            self.services.dialog_service.warning(
                "Konfigurasi Outlook Revisi", "Database aktif belum tersedia."
            )
            return
        self.services.task_runner.submit(
            lambda: module_service.load_detail(
                status.database_path, "OUTLOOK_REVISI"
            ),
            on_done=lambda result: (
                ModuleConfigurationDetailDialog(self, result.value)
                if result.success
                else self.services.dialog_service.warning(
                    "Konfigurasi Outlook Revisi", result.error
                )
            ),
        )

    def browse_output(self) -> None:
        path = self.services.dialog_service.select_folder(title="Pilih Output Root")
        if path:
            self.output_var.set(str(path))

    def open_configuration(self) -> None:
        path = Path(self.config_var.get()) if self.config_var.get().strip() else None
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Configuration", "Folder configuration tidak tersedia."
            )

    def _request(self) -> OutlookRevisiRunRequest:
        limit_text = self.message_limit_var.get().strip()
        try:
            limit = int(limit_text) if limit_text else None
        except ValueError as exc:
            raise ValueError("Email Limit harus berupa angka.") from exc
        fallback = self.config_var.get().strip()
        return OutlookRevisiRunRequest(
            configuration_path=Path(fallback) if fallback else None,
            workflow=self.workflow_var.get(),
            use_global_output=self.global_output_var.get(),
            use_global_period=False,
            override_output_root=Path(self.output_var.get().strip())
            if self.output_var.get().strip()
            else None,
            override_period_start=None,
            override_period_end=None,
            dry_run=self.dry_run_var.get(),
            message_limit=limit,
            payroll_period=self.payroll_period_var.get().strip() or None,
        )

    def validate_configuration(self) -> None:
        self._start_preflight(run_after=False, check_mailbox=False)

    def validate_mailbox(self) -> None:
        self._start_preflight(run_after=False, check_mailbox=True)

    def run_outlook(self) -> None:
        self._start_preflight(run_after=True, check_mailbox=True)

    def _start_preflight(self, *, run_after: bool, check_mailbox: bool) -> None:
        if self._busy:
            return
        try:
            request = self._request()
        except ValueError as exc:
            self.validation_summary.show_lines([str(exc)])
            return
        self._set_busy(True, "Validating Outlook Revisi...")

        def work():
            return self.services.outlook_revisi_service.preflight(
                request,
                require_database=run_after,
                check_mailbox=check_mailbox,
            )

        def done(task_result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not task_result.success:
                self.validation_summary.show_lines(
                    [task_result.error or "Validation failed"]
                )
                self.validation_summary.grid()
                self.validation_status_var.set("Perlu perhatian")
                return
            resolved, validation = task_result.value
            self._show_validation(validation)
            if not validation.valid or not run_after:
                return
            typed_confirmed = False
            if validation.outbound.requires_confirmation:
                if not self.outbound_ack_var.get():
                    self.services.dialog_service.warning(
                        "Outbound Safety",
                        "Centang outbound safety acknowledgement sebelum live run.",
                    )
                    return
                typed_confirmed = self.services.dialog_service.typed_confirm(
                    "Outbound SEND Confirmation",
                    "Mode live dapat mengirim email. Ketik SEND untuk melanjutkan.",
                    "SEND",
                )
                if not typed_confirmed:
                    return
            try:
                resolved = self.services.outlook_revisi_service.confirm_outbound(
                    resolved,
                    validation.outbound,
                    acknowledged=self.outbound_ack_var.get(),
                    typed_confirmed=typed_confirmed,
                )
            except ValueError as exc:
                self.services.dialog_service.warning("Outbound Safety", str(exc))
                return
            summary = (
                f"Workflow: {resolved.workflow}\n"
                f"Mailbox: {validation.mailbox.configured_mailbox}\n"
                f"Payroll Period: {resolved.payroll_period}\n"
                f"Output: {resolved.output_root}\n"
                f"Mode: {validation.outbound.effective_mode}\n\n"
                "Mulai job baru?"
            )
            if self.services.dialog_service.confirm("Run Outlook Revisi", summary):
                self._start_run(resolved)

        self.services.task_runner.submit(work, on_done=done)

    def _start_run(self, resolved) -> None:
        self._resolved = resolved
        self._cancellation = OutlookRevisiCancellationToken()
        self._running = True
        self._set_busy(True, "Outlook Revisi running...")
        self.cancel_button.configure(state="normal")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self._append_log(
            OutlookRevisiLogEvent("", "INFO", f"Job {resolved.job_id} confirmed.")
        )

        def work(report):
            return self.services.outlook_revisi_service.run_job(
                resolved,
                cancellation=self._cancellation,
                progress=report,
                log=report,
            )

        def done(task_result) -> None:
            if self._disposed:
                return
            self._running = False
            self.cancel_button.configure(state="disabled")
            self.cancel_button.pack_forget()
            self._set_busy(False)
            if task_result.success:
                self._last_result = task_result.value
                self._show_result(task_result.value)
            else:
                self.result_panel.grid()
                self.result_summary.show_lines(
                    [
                        "FAILED",
                        task_result.error or "Unexpected error",
                        "Gunakan output/log/configuration fallback secara manual.",
                    ]
                )

        self.services.task_runner.submit_reporting(
            work,
            on_done=done,
            on_progress=self._stream_event,
            cancellable=False,
        )

    def _stream_event(self, event) -> None:
        if self._disposed:
            return
        if isinstance(event, OutlookRevisiProgressEvent):
            self.progress.start(event.message)
        elif isinstance(event, OutlookRevisiLogEvent):
            self._append_log(event)

    def cancel(self) -> None:
        if not self._running or self._cancellation is None or self._resolved is None:
            return
        self._cancellation.request()
        self.cancel_button.configure(state="disabled")
        self.progress.start(
            "Pembatalan akan dilakukan pada safe checkpoint berikutnya."
        )
        self.services.task_runner.submit(
            lambda: self.services.outlook_revisi_service.request_cancellation(
                self._resolved, self._cancellation
            ),
            on_done=lambda result: None,
            cancellable=False,
        )

    def _show_validation(self, value) -> None:
        mailbox = value.mailbox
        outbound = value.outbound
        self.mailbox_status_var.set(
            f"Outlook: {mailbox.outlook_status} | Mailbox found: "
            f"{mailbox.mailbox_found} | Folder found: {mailbox.folder_found} | "
            f"{mailbox.mailbox_display or mailbox.configured_mailbox}"
        )
        previews = [
            f"Template {code}: {subject} | {body.replace(chr(10), ' / ')[:100]}"
            for code, subject, body in value.template_previews
        ]
        self.validation_summary.show_lines(
            [
                f"Configuration valid: {value.configuration_valid}",
                f"Workflow: {value.workflow}",
                f"Payroll Period: {value.period_start[5:7]}-{value.period_start[:4]}",
                f"Output: {value.output_root}",
                f"Sender / Subject / Attachment: {value.sender_count} / "
                f"{value.subject_rule_count} / {value.attachment_rule_count}",
                f"Validation Rules / Templates: {value.validation_rule_count} / "
                f"{value.reply_template_count}",
                f"Mailbox / Folder: {mailbox.configured_mailbox} / "
                f"{mailbox.configured_folder}",
                f"Auto Reply: {outbound.auto_reply_enabled}",
                f"Send Mode / Effective: {outbound.send_mode} / "
                f"{outbound.effective_mode}",
                f"Summary Email: {outbound.summary_email_enabled}",
                "Recipient scope: "
                + (
                    "; ".join(outbound.recipients) or "dynamic sender / none configured"
                ),
                f"Warnings / Errors: {len(value.warnings)} / {len(value.errors)}",
                *value.warnings,
                *value.errors,
                *previews,
            ]
        )
        self.validation_summary.grid()
        self.validation_status_var.set(
            "Siap" if value.valid else "Perlu perhatian"
        )

    def _show_result(self, result) -> None:
        status = (
            "CANCELLED"
            if result.cancelled
            else "COMPLETED WITH WARNING"
            if result.success and result.warning_count
            else "SUCCESS"
            if result.success
            else "FAILED"
        )
        self.result_summary.show_lines(
            [
                f"Status: {status}",
                f"Job ID: {result.job_id}",
                f"Workflow: {result.workflow}",
                f"Mailbox: {result.mailbox}",
                f"Email total/success/failed: "
                f"{result.message_counts.get('total', 0)} / "
                f"{result.message_counts.get('success', 0)} / "
                f"{result.message_counts.get('failed', 0)}",
                f"Attachments: {result.attachment_counts.get('total', 0)}",
                f"Accepted / ignored / rejected: "
                f"{result.attachment_counts.get('accepted', 0)} / "
                f"{result.attachment_counts.get('ignored', 0)} / "
                f"{result.attachment_counts.get('rejected', 0)}",
                f"Replies sent/drafted: {result.reply_counts.get('sent', 0)} / "
                f"{result.reply_counts.get('drafted', 0)}",
                f"Files: {len(result.output_files)}",
                f"Output: {result.output_root}",
                result.error_summary or "",
            ]
        )
        self.result_panel.grid()
        self.validation_status_var.set(
            "Dibatalkan"
            if result.cancelled
            else "Berhasil dengan peringatan"
            if result.success and result.warning_count
            else "Berhasil"
            if result.success
            else "Gagal"
        )

    def _append_log(self, event: OutlookRevisiLogEvent) -> None:
        stamp = event.timestamp or "session"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{stamp} [{event.level}] {event.message}\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 500:
            self.log_text.delete("1.0", f"{lines - 500}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def copy_log(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.log_text.get("1.0", "end-1c"))

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _apply_global_state(self) -> None:
        self.output_entry.configure(
            state="readonly" if self.global_output_var.get() else "normal"
        )
        self.output_browse.configure(
            state="disabled" if self.global_output_var.get() else "normal"
        )
        self.message_limit_entry.configure(
            state="readonly" if self.global_limit_var.get() else "normal",
            style="LimitReadonly.TEntry" if self.global_limit_var.get() else "Modern.TEntry",
        )

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.validate_config_button.configure(state=state)
        self.validate_mailbox_button.configure(state=state)
        self.run_button.configure(state=state)
        if busy:
            self.progress.start(message)
        else:
            self.progress.stop()

    def _result_path(self, attribute: str):
        return (
            getattr(self._last_result, attribute, None) if self._last_result else None
        )

    def _open_result_path(self, attribute: str, title: str) -> None:
        path = self._result_path(attribute)
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(title, "Path tidak tersedia.")

    def open_output(self) -> None:
        path = self._result_path("job_folder") or self._result_path("output_root")
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Output", "Output tidak tersedia."
            )

    def open_attachments(self) -> None:
        self._open_result_path("attachment_folder", "Open Attachments")

    def open_process_log(self) -> None:
        self._open_result_path("process_log_path", "Open Log")

    def retry(self) -> None:
        if not self._running:
            self._last_result = None
            self.result_summary.show_lines(
                ["Siap untuk job baru; tidak ada auto-retry."]
            )

    def return_settings(self) -> None:
        if not self._running and self.context.navigate:
            self.context.navigate("settings")

    def can_navigate_away(self) -> bool:
        return not self._running

    def dispose(self) -> None:
        self._disposed = True
        if self._cancellation is not None:
            self._cancellation.request()
