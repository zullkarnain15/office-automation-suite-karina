"""UI7B.1 compact Attendance pilot over the unchanged UI4 service boundary."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from ui.attendance_models import (
    AttendanceCancellationToken,
    AttendanceLogEvent,
    AttendanceProgressEvent,
    AttendanceRunRequest,
)
from ui.constants import COMPACT_LOG_BACKGROUND, LOG_FONT, LOG_TEXT
from ui.dialogs.module_configuration_detail import ModuleConfigurationDetailDialog
from ui.icon_manager import IconManager
from ui.pages.base_page import BasePage
from ui.widgets import (
    CompactProgress,
    DateEntry,
    OptionChip,
    ResultSummary,
    SegmentedChoice,
)


class AttendancePage(BasePage):
    page_id = "attendance"
    title = "Attendance"
    subtitle = "Ekstraksi dan validasi data mesin absensi."
    icon_name = "attendance.ico"
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self._defaults_loaded = False
        self._busy = False
        self._running = False
        self._disposed = False
        self._resolved = None
        self._cancellation = None
        self._last_result = None
        self._validation_lines: tuple[str, ...] = ()
        self._log_expanded = False
        self._run_icon = None
        self._open_folder_icon = None
        super().__init__(parent, context)
        self.configure(padding=(16, 10))

    def build_content(self) -> None:
        self.services = self.context.app_services
        self.config_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.output_summary_var = tk.StringVar(value="Output: Belum dikonfigurasi")
        self.workflow_var = tk.StringVar(value="HO")
        self.global_period_var = tk.BooleanVar(value=False)
        self.global_output_var = tk.BooleanVar(value=True)
        self.txt_var = tk.BooleanVar(value=True)
        self.report_var = tk.BooleanVar(value=True)
        self.advanced_var = tk.BooleanVar(value=False)
        self.manual_fallback_var = tk.BooleanVar(value=False)
        self.manual_output_var = tk.BooleanVar(value=False)
        self.validation_status_var = tk.StringVar(value="Belum diperiksa")
        self.active_config_var = tk.StringVar(
            value="Konfigurasi: OAS-K Database • Belum diperiksa"
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
            strip, textvariable=self.output_summary_var, style="CompactText.TLabel"
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
            text="Buka Settings",
            style="Attendance.TButton",
            command=self.return_settings,
        ).pack(side="left", padx=(6, 0))

    def _build_operational_panel(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 10))
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.operational_panel = panel
        self._operational_narrow = False
        self._operational_mode = None
        panel.columnconfigure(0, weight=5)
        panel.columnconfigure(1, weight=2)
        panel.columnconfigure(2, weight=2)

        period = ttk.Frame(panel, style="CompactBody.TFrame")
        self.period_section = period
        period.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        period.columnconfigure((0, 1), weight=1)
        ttk.Label(period, text="Periode", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(period, text="Tanggal Mulai", style="CompactText.TLabel").grid(
            row=1, column=0, sticky="w", pady=(5, 2)
        )
        ttk.Label(period, text="Tanggal Selesai", style="CompactText.TLabel").grid(
            row=1, column=1, sticky="w", padx=(10, 0), pady=(5, 2)
        )
        self.start_entry = DateEntry(period, textvariable=self.start_var, width=11)
        self.start_entry.grid(row=2, column=0, sticky="ew")
        self.end_entry = DateEntry(period, textvariable=self.end_var, width=11)
        self.end_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0))
        self.global_period_check = ttk.Checkbutton(
            period,
            text="Gunakan periode dari Settings",
            variable=self.global_period_var,
            command=self._apply_global_state,
        )
        self.global_period_check.grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )

        workflow = ttk.Frame(panel, style="CompactBody.TFrame")
        self.workflow_section = workflow
        workflow.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        ttk.Label(workflow, text="Workflow", style="CompactTitle.TLabel").pack(
            anchor="w"
        )
        self.workflow_segment = SegmentedChoice(
            workflow,
            variable=self.workflow_var,
            choices=(("HO", "HEAD OFFICE (HO)"), ("BRANCH", "BRANCH")),
        )
        self.workflow_choices = self.workflow_segment
        self.workflow_segment.pack(anchor="w", fill="x", pady=(6, 0))

        output = ttk.Frame(panel, style="CompactBody.TFrame")
        self.output_section = output
        output.grid(row=0, column=2, sticky="nsew")
        ttk.Label(output, text="Output", style="CompactTitle.TLabel").pack(anchor="w")
        OptionChip(output, text="HRIS TXT", variable=self.txt_var).pack(
            anchor="w", pady=(6, 2)
        )
        OptionChip(output, text="Excel Report", variable=self.report_var).pack(
            anchor="w"
        )
        panel.bind("<Configure>", self._layout_operational)

    def _layout_operational(self, event) -> None:
        narrow = event.width < 650
        scaling = float(self.tk.call("tk", "scaling"))
        mode = "narrow" if narrow else "compact" if event.width < 860 else "wide"
        if mode == self._operational_mode:
            return
        self._operational_mode = mode
        self._operational_narrow = narrow
        self.workflow_segment.buttons["HO"].configure(
            text="HO" if mode == "compact" and scaling >= 1.4 else "HEAD OFFICE (HO)"
        )
        for section in (
            self.period_section,
            self.workflow_section,
            self.output_section,
        ):
            section.grid_forget()
        if mode == "narrow":
            self.operational_panel.columnconfigure(0, weight=1)
            self.operational_panel.columnconfigure(1, weight=1)
            self.operational_panel.columnconfigure(2, weight=0)
            self.period_section.grid(
                row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8)
            )
            self.workflow_section.grid(row=1, column=0, sticky="nw", padx=(0, 14))
            self.output_section.grid(row=1, column=1, sticky="nw")
        elif mode == "compact":
            self.operational_panel.columnconfigure(0, weight=5)
            self.operational_panel.columnconfigure(1, weight=1)
            self.operational_panel.columnconfigure(2, weight=2)
            self.period_section.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            self.workflow_section.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
            self.output_section.grid(row=0, column=2, sticky="nsew")
        else:
            self.operational_panel.columnconfigure(0, weight=5)
            self.operational_panel.columnconfigure(1, weight=2)
            self.operational_panel.columnconfigure(2, weight=2)
            self.period_section.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
            self.workflow_section.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
            self.output_section.grid(row=0, column=2, sticky="nsew")

    def _build_action_row(self) -> None:
        row = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 7))
        row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        status = ttk.Frame(row, style="CompactBody.TFrame")
        status.grid(row=0, column=0, sticky="w")
        ttk.Label(status, text="Validasi:", style="CompactText.TLabel").pack(
            side="left"
        )
        self.validation_status = ttk.Label(
            status,
            textvariable=self.validation_status_var,
            style="StatusInfo.TLabel",
        )
        self.validation_status.pack(side="left", padx=(5, 0))
        self.validation_detail_button = ttk.Button(
            status,
            text="Lihat Detail",
            style="Attendance.TButton",
            command=self.show_validation_detail,
            state="disabled",
        )
        self.validation_detail_button.pack(side="left", padx=(8, 0))

        actions = ttk.Frame(row, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.validate_button = ttk.Button(
            actions,
            text="Periksa Data",
            style="Attendance.TButton",
            command=self.validate,
        )
        self.validate_button.pack(side="left", anchor="n")
        self.run_button = ttk.Button(
            actions,
            text="Start",
            style="AttendancePrimary.TButton",
            command=self.run_attendance,
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

        # Compatibility detail model retained for fixture acceptance assertions.
        self.validation_summary = ResultSummary(row, wraplength=680)
        self.validation_summary.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.validation_summary.grid_remove()

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
        actions = ttk.Frame(header, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.log_expand_button = ttk.Button(
            actions,
            text="Perbesar Log",
            style="Compact.TButton",
            command=self.toggle_log,
        )
        self.log_expand_button.pack(side="left")
        ttk.Button(
            actions,
            text="Buka Log",
            style="Compact.TButton",
            command=self.open_process_log,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            actions, text="Salin", style="Compact.TButton", command=self.copy_log
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
        self._append_log(AttendanceLogEvent("", "INFO", "Application ready."))

    def _build_result(self) -> None:
        self.result_panel = ttk.Frame(
            self.surface, style="CompactPanel.TFrame", padding=(10, 8)
        )
        self.result_panel.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.result_panel.columnconfigure(0, weight=1)
        self.result_summary = ResultSummary(self.result_panel, wraplength=720)
        self.result_summary.grid(row=0, column=0, sticky="ew")
        actions = ttk.Frame(self.result_panel, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e", padx=(10, 0))
        for text, command in (
            ("Buka Output", self.open_output),
            ("Buka Report", self.open_report),
            ("Buka Log", self.open_process_log),
        ):
            if self._open_folder_icon is None:
                self._open_folder_icon = IconManager(
                    self.context.assets_path / "icons",
                    master=self.winfo_toplevel(),
                    logger=self.context.logger,
                ).load("open_folder.ico", size=16)
            button = ttk.Button(
                actions, text=text, style="Attendance.TButton", command=command
            )
            if self._open_folder_icon is not None:
                button.configure(image=self._open_folder_icon, compound="left")
            button.pack(side="left", padx=(6, 0))
        self.result_panel.grid_remove()

    def _build_advanced(self) -> None:
        section = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(10, 6))
        section.grid(row=6, column=0, sticky="ew")
        self.advanced_section = section
        section.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            section,
            text="Advanced / Manual Fallback",
            variable=self.advanced_var,
            command=self._toggle_advanced,
        ).grid(row=0, column=0, sticky="w")
        self.advanced_frame = ttk.Frame(section, style="CompactBody.TFrame")
        self.advanced_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.advanced_frame.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            self.advanced_frame,
            text="Gunakan workbook konfigurasi sementara",
            variable=self.manual_fallback_var,
            command=self._toggle_fallback,
        ).grid(row=0, column=0, sticky="w")
        self.fallback_frame = ttk.Frame(self.advanced_frame, style="CompactBody.TFrame")
        self.fallback_frame.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        self.fallback_frame.columnconfigure(0, weight=1)
        ttk.Entry(self.fallback_frame, textvariable=self.config_var).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            self.fallback_frame,
            text="Pilih Excel",
            style="Compact.TButton",
            command=self.browse_configuration,
        ).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(
            self.fallback_frame,
            text="Buka Folder",
            style="Compact.TButton",
            command=self.open_configuration,
        ).grid(row=0, column=2, padx=(6, 0))
        self.fallback_frame.grid_remove()

        ttk.Checkbutton(
            self.advanced_frame,
            text="Gunakan folder output lain untuk proses ini",
            variable=self.manual_output_var,
            command=self._toggle_output_override,
        ).grid(row=2, column=0, sticky="w")
        self.output_override_frame = ttk.Frame(
            self.advanced_frame, style="CompactBody.TFrame"
        )
        self.output_override_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        self.output_override_frame.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(
            self.output_override_frame, textvariable=self.output_var
        )
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_browse = ttk.Button(
            self.output_override_frame,
            text="Browse",
            style="Compact.TButton",
            command=self.browse_output,
        )
        self.output_browse.grid(row=0, column=1, padx=(6, 0))
        self.output_override_frame.grid_remove()
        self.advanced_frame.grid_remove()

    def on_show(self) -> None:
        if not self._busy and not self._running:
            self._load_defaults()

    def _load_defaults(self) -> None:
        self._set_busy(True, "Memuat konfigurasi Attendance...")

        def work():
            service = self.services.attendance_service
            summary_loader = getattr(service, "load_active_configuration", None)
            return service.load_defaults(), (
                summary_loader() if callable(summary_loader) else None
            )

        def done(result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not result.success:
                self._set_validation_status("Perlu perhatian", "StatusWarning.TLabel")
                self._validation_lines = (result.error or "Defaults unavailable",)
                self.validation_summary.show_lines(self._validation_lines)
                return
            value, summary = result.value
            self._defaults_loaded = True
            self._defaults = value
            if value.global_output_root:
                self.output_var.set(str(value.global_output_root))
                self.output_summary_var.set(f"Output: {value.global_output_root}")
            if value.global_period_start:
                self.start_entry.set_iso(value.global_period_start)
            if value.global_period_end:
                self.end_entry.set_iso(value.global_period_end)
            self.global_output_var.set(
                value.use_global_output and value.global_output_root is not None
            )
            self.manual_output_var.set(not self.global_output_var.get())
            self.global_period_var.set(
                value.use_global_period
                and bool(value.global_period_start and value.global_period_end)
            )
            if not value.database_available:
                self.global_period_check.configure(state="disabled")
                self._set_validation_status(
                    "Belum dikonfigurasi", "StatusWarning.TLabel"
                )
                self._validation_lines = (value.warning,)
                self.validation_summary.show_lines(self._validation_lines)
                self.active_config_var.set(
                    "Konfigurasi: OAS-K Database • Belum dikonfigurasi"
                )
            elif summary is not None:
                fields = " • ".join(
                    f"{key.replace(' Sources', '')} {item.replace(' aktif', '')}"
                    for key, item in summary.fields[:2]
                )
                self.active_config_var.set(
                    "Konfigurasi: OAS-K Database"
                    + (f" • {fields}" if fields else "")
                    + f" • Diperbarui: {summary.last_updated or '-'}"
                )
                self._set_validation_status("Siap", "StatusReady.TLabel")
            self._toggle_output_override()
            self._apply_global_state()

        self.services.task_runner.submit(work, on_done=done)

    def browse_configuration(self) -> None:
        path = self.services.dialog_service.select_file(
            title="Pilih Attendance Configuration",
            filetypes=(("Excel Workbook", "*.xlsx"),),
        )
        if path:
            self.config_var.set(str(path))
            self.advanced_var.set(True)
            self.manual_fallback_var.set(True)
            self._toggle_advanced()
            self._toggle_fallback()

    def browse_output(self) -> None:
        path = self.services.dialog_service.select_folder(title="Pilih Output Root")
        if path:
            self.output_var.set(str(path))
            self.output_summary_var.set(f"Output override: {path}")

    def _toggle_advanced(self) -> None:
        if self.advanced_var.get():
            if self._log_expanded:
                self.toggle_log()
            self.advanced_frame.grid()
            if not self._log_expanded:
                self.log_text.configure(height=3)
        else:
            self.advanced_frame.grid_remove()
            self.log_text.configure(height=10 if self._log_expanded else 5)

    def _toggle_fallback(self) -> None:
        if self.manual_fallback_var.get():
            self.fallback_frame.grid()
        else:
            self.fallback_frame.grid_remove()
            self.config_var.set("")

    def _toggle_output_override(self) -> None:
        manual = self.manual_output_var.get()
        self.global_output_var.set(not manual)
        if manual:
            self.output_override_frame.grid()
        else:
            self.output_override_frame.grid_remove()
            defaults = getattr(self, "_defaults", None)
            if defaults is not None and defaults.global_output_root:
                self.output_var.set(str(defaults.global_output_root))
                self.output_summary_var.set(f"Output: {defaults.global_output_root}")

    def refresh_active_configuration(self) -> None:
        if not self._busy:
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
                "Konfigurasi Attendance", "Database aktif belum tersedia."
            )
            return
        self.services.task_runner.submit(
            lambda: module_service.load_detail(status.database_path, "ATTENDANCE"),
            on_done=lambda result: (
                ModuleConfigurationDetailDialog(self, result.value)
                if result.success
                else self.services.dialog_service.warning(
                    "Konfigurasi Attendance", result.error
                )
            ),
        )

    def open_configuration(self) -> None:
        path = Path(self.config_var.get()) if self.config_var.get().strip() else None
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Configuration", "Folder tidak tersedia."
            )

    def _request(self) -> AttendanceRunRequest:
        fallback = self.config_var.get().strip()
        return AttendanceRunRequest(
            Path(fallback) if fallback else None,
            self.workflow_var.get(),
            self.global_output_var.get(),
            self.global_period_var.get(),
            Path(self.output_var.get().strip())
            if self.output_var.get().strip()
            else None,
            self.start_entry.get_iso(),
            self.end_entry.get_iso(),
            self.txt_var.get(),
            self.report_var.get(),
        )

    def validate(self) -> None:
        try:
            request = self._request()
        except ValueError as exc:
            self._show_validation_error(str(exc))
            return
        self._preflight(request, run_after=False)

    def run_attendance(self) -> None:
        try:
            request = self._request()
        except ValueError as exc:
            self._show_validation_error(str(exc))
            return
        self._preflight(request, run_after=True)

    def _preflight(self, request, *, run_after: bool) -> None:
        if self._busy:
            return
        self._set_busy(True, "Memeriksa data Attendance...")

        def work():
            return self.services.attendance_service.preflight(
                request, require_database=run_after
            )

        def done(task_result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not task_result.success:
                self._show_validation_error(task_result.error or "Validation failed")
                return
            resolved, validation = task_result.value
            self._show_validation(validation)
            if not validation.valid or not run_after:
                return
            summary = (
                f"Workflow: {resolved.workflow}\n"
                f"Period: {resolved.period_start} – {resolved.period_end}\n"
                f"Output: {resolved.output_root}\n"
                f"TXT: {resolved.generate_txt}\nReport: {resolved.generate_report}"
            )
            if self.services.dialog_service.confirm(
                "Jalankan Attendance", summary + "\n\nMulai job baru?"
            ):
                self._start_run(resolved)

        self.services.task_runner.submit(work, on_done=done)

    def _start_run(self, resolved) -> None:
        self._resolved = resolved
        self._cancellation = AttendanceCancellationToken()
        self._running = True
        self._set_validation_status("Sedang berjalan", "StatusRunning.TLabel")
        self._set_busy(True, "Attendance sedang berjalan...")
        self.cancel_button.configure(state="normal")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self._append_log(
            AttendanceLogEvent("", "INFO", f"Job {resolved.job_id} confirmed.")
        )

        def work(report):
            return self.services.attendance_service.run_job(
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
                self._set_validation_status("Gagal", "StatusError.TLabel")
                self.result_panel.grid()
                self.result_summary.show_lines(
                    (
                        "FAILED",
                        task_result.error or "Unexpected error",
                        "Periksa konfigurasi, output, dan process log.",
                    )
                )

        self.services.task_runner.submit_reporting(
            work, on_done=done, on_progress=self._stream_event, cancellable=False
        )

    def _stream_event(self, event) -> None:
        if self._disposed:
            return
        if isinstance(event, AttendanceProgressEvent):
            self.progress.start(event.message)
        elif isinstance(event, AttendanceLogEvent):
            self._append_log(event)

    def cancel(self) -> None:
        if not self._running or self._cancellation is None or self._resolved is None:
            return
        self._cancellation.request()
        self.cancel_button.configure(state="disabled")
        self.progress.start("Pembatalan menunggu checkpoint aman...")
        self.services.task_runner.submit(
            lambda: self.services.attendance_service.request_cancellation(
                self._resolved, self._cancellation
            ),
            on_done=lambda result: None,
            cancellable=False,
        )

    def _show_validation(self, value) -> None:
        self._validation_lines = (
            f"Configuration valid: {value.configuration_valid}",
            f"Workflow: {value.workflow}",
            f"Active MDB: {value.active_mdb_count}",
            f"Period: {value.period_start} – {value.period_end}",
            f"Output: {value.output_root}",
            f"Generate TXT: {value.generate_txt}",
            f"Generate Report: {value.generate_report}",
            f"Warnings: {len(value.warnings)}",
            f"Errors: {len(value.errors)}",
            *value.warnings,
            *value.errors,
            *(
                f"{item.name}: {item.status} | {item.mdb_path}"
                for item in value.sources
            ),
        )
        self.validation_summary.show_lines(self._validation_lines)
        if value.valid:
            self._set_validation_status(
                f"Siap • {value.active_mdb_count} sumber {value.workflow} aktif"
            )
        else:
            self._set_validation_status("Perlu perhatian")
        self.validation_detail_button.configure(state="normal")

    def _show_validation_error(self, message: str) -> None:
        self._validation_lines = (message,)
        self.validation_summary.show_lines(self._validation_lines)
        self._set_validation_status("Perlu perhatian", "StatusWarning.TLabel")
        self.validation_detail_button.configure(state="normal")

    def show_validation_detail(self) -> None:
        if not self._validation_lines:
            return
        info = getattr(self.services.dialog_service, "info", None)
        if callable(info):
            info("Detail Validasi Attendance", "\n".join(self._validation_lines))
        else:
            self.validation_summary.grid()

    def _show_result(self, result) -> None:
        status = (
            "CANCELLED"
            if result.cancelled
            else "SUCCESS"
            if result.success
            else "FAILED"
        )
        try:
            duration = max(
                0,
                int(
                    (
                        datetime.fromisoformat(result.ended_at)
                        - datetime.fromisoformat(result.started_at)
                    ).total_seconds()
                ),
            )
            duration_text = (
                f"{duration // 3600:02}:{duration % 3600 // 60:02}:{duration % 60:02}"
            )
        except ValueError:
            duration_text = "-"
        reports = sum(
            "REPORT" in item.file_type.upper() for item in result.output_files
        )
        txt_files = sum("TXT" in item.file_type.upper() for item in result.output_files)
        self.result_summary.show_lines(
            (
                f"Status: {status} • TXT: {txt_files} file • Report: {reports} file • Durasi: {duration_text}",
                f"Job: {result.job_id} • Valid: {result.record_counts.get('valid', 0)} • Anomaly: {result.record_counts.get('anomaly', 0)}",
                result.error_summary or "",
            )
        )
        self.result_panel.grid()
        self._set_validation_status(
            "Gagal"
            if not result.success and not result.cancelled
            else "Siap"
            if result.success
            else "Dibatalkan"
        )
        if result.success:
            completion = getattr(self.services.dialog_service, "completion", None)
            if callable(completion):
                completion(
                    "Attendance",
                    "Attendance berhasil diproses. Output sudah tersimpan dan siap digunakan.",
                    (
                        f"Valid: {result.record_counts.get('valid', 0)} | Anomaly: {result.record_counts.get('anomaly', 0)}",
                        f"TXT: {txt_files} file | Report: {reports} file | Durasi: {duration_text}",
                        f"Output: {result.output_root}",
                    ),
                )

    def _set_validation_status(self, text: str, style: str | None = None) -> None:
        if style is None:
            normalized = text.casefold()
            if normalized.startswith("siap"):
                style = "StatusReady.TLabel"
            elif normalized.startswith("gagal"):
                style = "StatusError.TLabel"
            elif normalized.startswith(("perlu perhatian", "belum dikonfigurasi")):
                style = "StatusWarning.TLabel"
            elif normalized.startswith("sedang berjalan"):
                style = "StatusRunning.TLabel"
            elif normalized.startswith(("dibatalkan", "belum diperiksa")):
                style = "StatusInfo.TLabel"
            else:
                style = "CompactStatus.TLabel"
        self.validation_status_var.set(text)
        self.validation_status.configure(style=style)

    def _append_log(self, event: AttendanceLogEvent) -> None:
        stamp = event.timestamp or "session"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{stamp} [{event.level}] {event.message}\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 500:
            self.log_text.delete("1.0", f"{lines - 500}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def toggle_log(self) -> None:
        self._log_expanded = not self._log_expanded
        if self._log_expanded:
            self.progress_panel.grid_remove()
            self.advanced_section.grid_remove()
        else:
            self.progress_panel.grid()
            self.advanced_section.grid()
        self.log_text.configure(height=10 if self._log_expanded else 5)
        self.log_expand_button.configure(
            text="Perkecil Log" if self._log_expanded else "Perbesar Log"
        )

    def copy_log(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.log_text.get("1.0", "end-1c"))

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _apply_global_state(self) -> None:
        state = "readonly" if self.global_period_var.get() else "normal"
        self.start_entry.configure(state=state)
        self.end_entry.configure(state=state)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.validate_button.configure(state=state)
        self.run_button.configure(state=state)
        if busy:
            self.progress.start(message)
        else:
            self.progress.stop()

    def _result_path(self, attribute: str):
        return (
            getattr(self._last_result, attribute, None) if self._last_result else None
        )

    def open_output(self) -> None:
        path = self._result_path("job_folder") or self._result_path("output_root")
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Output", "Output tidak tersedia."
            )

    def open_report(self) -> None:
        path = None
        if self._last_result:
            path = next(
                (
                    item.path
                    for item in self._last_result.output_files
                    if "REPORT" in item.file_type.upper()
                ),
                None,
            )
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Report", "Report tidak tersedia."
            )

    def open_process_log(self) -> None:
        path = self._result_path("process_log_path")
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Log", "Process.log tidak tersedia."
            )

    def retry(self) -> None:
        if not self._running:
            self._last_result = None
            self.result_panel.grid_remove()
            self._set_validation_status("Belum diperiksa", "StatusInfo.TLabel")

    def return_settings(self) -> None:
        if not self._running and self.context.navigate:
            self.context.navigate("settings")

    def can_navigate_away(self) -> bool:
        return not self._running

    def dispose(self) -> None:
        self._disposed = True
        if self._cancellation is not None:
            self._cancellation.request()
