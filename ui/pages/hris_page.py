"""Compact HRIS assisted-upload page over the unchanged service boundary."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ui.constants import COMPACT_LOG_BACKGROUND, LOG_FONT, LOG_TEXT
from ui.dialogs.module_configuration_detail import ModuleConfigurationDetailDialog
from ui.icon_manager import IconManager
from ui.global_hotkey import WindowsGlobalHotkey
from ui.hris_models import (
    HRISCancellationToken,
    HRISInterventionRequest,
    HRISJobState,
    HRISLogEvent,
    HRISProgressEvent,
    HRISRunRequest,
)
from ui.pages.base_page import BasePage
from ui.widgets import (
    CompactProgress,
    DateEntry,
    OptionChip,
    ResultSummary,
    SegmentedChoice,
)


class HRISPage(BasePage):
    page_id = "hris"
    title = "HRIS"
    subtitle = "Assisted upload attendance dengan recorder profile HRIS."
    icon_name = "hris.ico"
    show_page_heading = False

    def __init__(self, parent, context) -> None:
        self._busy = False
        self._running = False
        self._disposed = False
        self._defaults_loaded = False
        self._resolved = None
        self._cancellation = None
        self._last_result = None
        self._data_root = None
        self._run_icon = None
        self._open_folder_icon = None
        self._intervention_state = None
        super().__init__(parent, context)
        self.configure(padding=(16, 10))

    def build_content(self) -> None:
        self.services = self.context.app_services
        self.active_config_var = tk.StringVar(
            value="Konfigurasi: OAS-K Database - Belum diperiksa"
        )
        self.source_var = tk.StringVar()
        self.source_summary_var = tk.StringVar(value="TXT source: Belum dipilih")
        self.workflow_var = tk.StringVar(value="HO")
        self.global_period_var = tk.BooleanVar(value=False)
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.profile_var = tk.StringVar()
        self.profile_status_var = tk.StringVar(value="Profile belum diperiksa.")
        self.fallback_var = tk.BooleanVar(value=False)
        self.fallback_path_var = tk.StringVar()
        self.manual_ack_var = tk.BooleanVar(value=False)
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.intervention_file_var = tk.StringVar(value="-")
        self.intervention_control_var = tk.StringVar(value="-")
        self.intervention_status_var = tk.StringVar(value="Tidak ada tindakan manual.")

        self.surface = ttk.Frame(self, style="OASK.TFrame")
        self.surface.grid(row=1, column=0, sticky="nsew")
        self.surface.columnconfigure(0, weight=1)
        self.surface.rowconfigure(5, weight=1)

        self._build_configuration_strip()
        self._build_operational_panel()
        self._build_action_row()
        self._build_intervention_panel()
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
            strip, textvariable=self.source_summary_var, style="CompactText.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_operational_panel(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 10))
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=4)
        panel.columnconfigure(1, weight=3)
        panel.columnconfigure(2, weight=3)
        panel.rowconfigure(1, weight=1)

        source = ttk.Frame(panel, style="CompactBody.TFrame")
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        source.columnconfigure(0, weight=1)
        ttk.Label(source, text="TXT Source", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            source, text="Folder TXT Attendance", style="CompactText.TLabel"
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 2))
        ttk.Entry(source, textvariable=self.source_var, style="Modern.TEntry").grid(
            row=2, column=0, sticky="ew"
        )
        ttk.Button(
            source, text="Browse", style="Attendance.TButton", command=self.browse_source
        ).grid(row=2, column=1, padx=(6, 0))

        period = ttk.Frame(panel, style="CompactBody.TFrame")
        period.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        period.columnconfigure((0, 1), weight=1)
        ttk.Label(period, text="Periode & Workflow", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.global_period_check = OptionChip(
            period,
            text="Gunakan periode dari Settings",
            variable=self.global_period_var,
            command=self._apply_global_period_state,
        )
        self.global_period_check.grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(5, 2)
        )
        ttk.Label(period, text="Mulai", style="CompactText.TLabel").grid(
            row=2, column=0, sticky="w", pady=(3, 2)
        )
        ttk.Label(period, text="Selesai", style="CompactText.TLabel").grid(
            row=2, column=1, sticky="w", padx=(10, 0), pady=(3, 2)
        )
        self.start_entry = DateEntry(
            period, textvariable=self.start_var, width=11
        )
        self.start_entry.grid(row=3, column=0, sticky="ew")
        self.end_entry = DateEntry(
            period, textvariable=self.end_var, width=11
        )
        self.end_entry.grid(row=3, column=1, sticky="ew", padx=(10, 0))
        workflow = ttk.Frame(period, style="CompactBody.TFrame")
        workflow.grid(row=4, column=0, columnspan=2, sticky="w", pady=(7, 0))
        SegmentedChoice(
            workflow,
            variable=self.workflow_var,
            choices=(("HO", "HO"), ("BRANCH", "BRANCH")),
        ).pack(anchor="w")

        profile = ttk.Frame(panel, style="CompactBody.TFrame")
        profile.grid(row=0, column=2, sticky="nsew")
        profile.columnconfigure(0, weight=1)
        ttk.Label(profile, text="Recorder Profile", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Entry(
            profile,
            textvariable=self.profile_var,
            style="Readonly.TEntry",
            state="readonly",
        ).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(5, 6))
        ttk.Button(
            profile, text="Pilih", style="Attendance.TButton", command=self.select_profile
        ).grid(row=2, column=0, sticky="w")
        ttk.Button(
            profile,
            text="Validate",
            style="Attendance.TButton",
            command=self.validate_only,
        ).grid(row=2, column=1, sticky="w", padx=(6, 0))
        ttk.Button(
            profile,
            text="Folder",
            style="Attendance.TButton",
            command=self.open_profile_folder,
        ).grid(row=2, column=2, sticky="w", padx=(6, 0))
        self.calibrate_button = ttk.Button(
            profile,
            text="Kalibrasi Ulang",
            style="Attendance.TButton",
            command=self.calibrate_profile,
        )
        self.calibrate_button.grid(row=2, column=3, sticky="w", padx=(6, 0))
        self.profile_status_label = ttk.Label(
            profile,
            textvariable=self.profile_status_var,
            wraplength=280,
            style="StatusInfo.TLabel",
        )
        self.profile_status_label.grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(6, 0)
        )

        login = ttk.Frame(panel, style="CompactBody.TFrame")
        login.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        login.columnconfigure(1, weight=1)
        login.columnconfigure(3, weight=1)
        ttk.Label(login, text="Login HRIS", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(login, text="Username HRIS", style="CompactText.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 2)
        )
        self.username_entry = ttk.Entry(
            login,
            textvariable=self.username_var,
            style="Modern.TEntry",
        )
        self.username_entry.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 10))
        ttk.Label(login, text="Password HRIS", style="CompactText.TLabel").grid(
            row=1, column=2, sticky="w", pady=(8, 2)
        )
        self.password_entry = ttk.Entry(
            login,
            textvariable=self.password_var,
            show="*",
            style="Modern.TEntry",
        )
        self.password_entry.grid(row=2, column=2, columnspan=2, sticky="ew")
        self.login_hint_var = tk.StringVar(
            value="Username/password hanya dipakai untuk sesi ini dan tidak disimpan."
        )
        ttk.Label(
            login,
            textvariable=self.login_hint_var,
            style="CompactText.TLabel",
            wraplength=760,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def _build_action_row(self) -> None:
        row = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 7))
        row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        self.validation_summary = ResultSummary(row, wraplength=700)
        self.validation_summary.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.validation_summary.grid_remove()
        status = ttk.Frame(row, style="CompactBody.TFrame")
        status.grid(row=0, column=0, sticky="w")
        ttk.Label(
            status,
            text="Upload, Run, dan OK dijalankan dari recorder profile",
            style="CompactStatus.TLabel",
        ).pack(side="left")
        actions = ttk.Frame(row, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.manual_ack_check = OptionChip(
            actions, text="Automation klik dipahami", variable=self.manual_ack_var
        )
        self.manual_ack_check.pack(side="left")
        self.validate_button = ttk.Button(
            actions,
            text="Periksa Data",
            style="Attendance.TButton",
            command=self.validate_only,
        )
        self.validate_button.pack(side="left", padx=(8, 0))
        self.run_button = ttk.Button(
            actions,
            text="Start",
            command=self.run_hris,
            style="AttendancePrimary.TButton",
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
            command=self.cancel,
            state="disabled",
            style="AttendanceDanger.TButton",
        )
        self.cancel_button.pack(side="left", padx=(8, 0), anchor="n")
        self.cancel_button.pack_forget()

    def _build_intervention_panel(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 8))
        panel.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=1)
        self.intervention_status_label = ttk.Label(
            panel,
            textvariable=self.intervention_status_var,
            style="CompactStatus.TLabel",
            wraplength=850,
        )
        self.intervention_status_label.grid(row=0, column=0, sticky="w")
        ttk.Label(
            panel, textvariable=self.intervention_file_var, style="CompactText.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(
            panel,
            textvariable=self.intervention_control_var,
            style="CompactText.TLabel",
        ).grid(row=2, column=0, sticky="w")
        manual_actions = ttk.Frame(panel, style="CompactBody.TFrame")
        manual_actions.grid(row=0, column=1, rowspan=3, sticky="e", padx=(12, 0))
        self.login_continue_button = ttk.Button(
            manual_actions,
            text="Login Selesai",
            command=self.confirm_login,
            state="disabled",
            style="Attendance.TButton",
        )
        self.login_continue_button.pack(side="left")
        self.upload_continue_button = ttk.Button(
            manual_actions,
            text="Lanjutkan",
            command=self.confirm_upload,
            state="disabled",
            style="AttendancePrimary.TButton",
        )
        self.upload_continue_button.pack(side="left", padx=(6, 0))
        self.upload_failed_button = ttk.Button(
            manual_actions,
            text="Tandai Gagal",
            command=self.report_upload_failed,
            state="disabled",
            style="AttendanceDanger.TButton",
        )
        self.upload_failed_button.pack(side="left", padx=(6, 0))
        self.verification_retry_button = ttk.Button(
            manual_actions,
            text="Periksa Ulang",
            command=lambda: self.choose_intervention("retry"),
            state="disabled",
            style="Attendance.TButton",
        )
        self.verification_retry_button.pack(side="left", padx=(6, 0))
        self.intervention_stop_button = ttk.Button(
            manual_actions,
            text="Hentikan",
            command=lambda: self.choose_intervention("stop"),
            state="disabled",
            style="AttendanceDanger.TButton",
        )
        self.intervention_stop_button.pack(side="left", padx=(6, 0))

    def _build_progress(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(12, 6))
        panel.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=1)
        self.progress = CompactProgress(panel)
        self.progress.grid(row=0, column=0, sticky="ew")

    def _build_log(self) -> None:
        panel = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(10, 8))
        panel.grid(row=5, column=0, sticky="nsew", pady=(0, 8))
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
            log_actions, text="Salin", style="Attendance.TButton", command=self.copy_log
        ).pack(side="left")
        ttk.Button(
            log_actions,
            text="Bersihkan",
            style="Attendance.TButton",
            command=self.clear_log,
        ).pack(side="left", padx=(6, 0))
        self.log_text = tk.Text(
            panel,
            height=5,
            state="disabled",
            wrap="word",
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
        self.result_panel.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.result_panel.columnconfigure(0, weight=1)
        self.result_summary = ResultSummary(self.result_panel, wraplength=720)
        self.result_summary.grid(row=0, column=0, sticky="ew")
        recovery = ttk.Frame(self.result_panel, style="CompactBody.TFrame")
        recovery.grid(row=0, column=1, sticky="e", padx=(10, 0))
        for text, command in (
            ("Buka Source", self.open_source_folder),
            ("Buka Uploaded", self.open_output_folder),
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
        self.mapping_tree = ttk.Treeview(
            self.result_panel,
            columns=("sequence", "id", "workflow", "status"),
            show="headings",
            height=3,
        )
        for name, title, width in (
            ("sequence", "Seq", 42),
            ("id", "Run Control ID", 120),
            ("workflow", "Workflow", 70),
            ("status", "Status", 90),
        ):
            self.mapping_tree.heading(name, text=title)
            self.mapping_tree.column(name, width=width, stretch=name == "id")
        self.mapping_tree.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.result_panel.grid_remove()

    def _build_advanced(self) -> None:
        section = ttk.Frame(self.surface, style="CompactPanel.TFrame", padding=(10, 6))
        section.grid(row=7, column=0, sticky="ew")
        section.columnconfigure(0, weight=1)
        self.fallback_check = ttk.Checkbutton(
            section,
            text="Advanced / Manual Fallback",
            variable=self.fallback_var,
            command=self._toggle_fallback,
        )
        self.fallback_check.grid(row=0, column=0, sticky="w")
        self.fallback_frame = ttk.Frame(section, style="CompactBody.TFrame")
        self.fallback_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.fallback_frame.columnconfigure(0, weight=1)
        ttk.Entry(
            self.fallback_frame,
            textvariable=self.fallback_path_var,
            style="Modern.TEntry",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            self.fallback_frame,
            text="Pilih Excel",
            style="Attendance.TButton",
            command=self.browse_fallback,
        ).grid(row=0, column=1, padx=(6, 0))
        self.fallback_frame.grid_remove()

    def on_show(self) -> None:
        if not self._busy and not self._running:
            self._load_defaults()

    def _load_defaults(self) -> None:
        self._set_busy(True, "Membaca konfigurasi HRIS...")

        def done(result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not result.success:
                self.validation_summary.show_lines(
                    [result.error or "Gagal membaca HRIS."]
                )
                self.validation_summary.grid()
                return
            value = result.value
            self._defaults_loaded = True
            self._data_root = value.data_root
            self.active_config_var.set(
                f"Konfigurasi: OAS-K Database - "
                f"{'Siap' if value.database_available else 'Tidak Tersedia'} - "
                f"URL: {value.hris_url or '-'} - Browser: {value.browser} - "
                f"HO: {len(value.ho_run_controls)} - "
                f"BRANCH: {len(value.branch_run_controls)} - "
                f"Updated: {value.last_updated or '-'}"
            )
            if value.global_period_start:
                self.start_entry.set_iso(value.global_period_start)
            if value.global_period_end:
                self.end_entry.set_iso(value.global_period_end)
            self.global_period_var.set(
                value.use_global_period
                and bool(value.global_period_start and value.global_period_end)
            )
            if value.recorder_profile:
                self.profile_var.set(str(value.recorder_profile))
            self._apply_global_period_state()
            if value.warning:
                self.validation_summary.show_lines([value.warning])
                self.validation_summary.grid()

        self.services.task_runner.submit(
            self.services.hris_service.load_defaults, on_done=done
        )

    def refresh_active_configuration(self) -> None:
        if not self._busy:
            self._defaults_loaded = False
            self._load_defaults()

    def refresh_source(self) -> None:
        raw = self.source_var.get().strip()
        if not raw:
            self.source_summary_var.set("Folder TXT wajib dipilih.")
            return
        self.services.task_runner.submit(
            lambda: self.services.hris_service.discover_txt(Path(raw)),
            on_done=lambda result: self.source_summary_var.set(
                f"TXT ditemukan/valid: {len(result.value)}"
                if result.success
                else result.error or "Discovery gagal."
            ),
        )

    def _request(self) -> HRISRunRequest:
        fallback = self.fallback_path_var.get().strip()
        profile = self.profile_var.get().strip()
        return HRISRunRequest(
            Path(self.source_var.get().strip()),
            self.workflow_var.get(),
            self.global_period_var.get(),
            self.start_entry.get_iso(),
            self.end_entry.get_iso(),
            Path(profile) if profile else None,
            self.manual_ack_var.get(),
            Path(fallback) if self.fallback_var.get() and fallback else None,
            False,
            self.username_var.get().strip() or None,
            self.password_var.get() or None,
        )

    def validate_only(self) -> None:
        self._preflight(run_after=False)

    def run_hris(self) -> None:
        self._preflight(run_after=True)

    def calibrate_profile(self) -> None:
        if self._busy:
            return
        if not self.services.dialog_service.confirm(
            "Kalibrasi Ulang HRIS",
            (
                "Microsoft Edge akan dibuka untuk HRIS.\n\n"
                "Login dan navigasi manual sampai halaman Overtime Upload "
                "Attendance siap. Setelah itu OAS-K akan meminta koordinat "
                "untuk setiap langkah.\n\n"
                "Mulai kalibrasi sekarang?"
            ),
        ):
            return
        self._set_busy(True, "Kalibrasi HRIS recorder profile...")
        self._set_profile_status("Kalibrasi berjalan...")

        def done(result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not result.success:
                self._set_profile_status("Kalibrasi gagal.")
                self.validation_summary.show_lines(
                    [result.error or "Kalibrasi gagal."]
                )
                self.validation_summary.grid()
                return
            self.profile_var.set(str(result.value))
            self._set_profile_status("Profile tersimpan. Klik Validate untuk cek.")
            self.validation_summary.show_lines(
                [
                    "Kalibrasi selesai.",
                    f"Recorder profile: {result.value}",
                ]
            )
            self.validation_summary.grid()
            self.refresh_active_configuration()

        self.services.task_runner.submit(
            lambda: self.services.hris_service.calibrate_profile(
                self.workflow_var.get(),
                instruction_callback=self._wait_for_calibration_navigation,
                coordinate_callback=self._capture_calibration_point,
            ),
            on_done=done,
            cancellable=False,
        )

    def _preflight(self, *, run_after: bool) -> None:
        if self._busy:
            return
        try:
            request = self._request()
        except Exception as exc:
            self.validation_summary.show_lines([str(exc)])
            self.validation_summary.grid()
            return
        self._set_busy(True, "Validating HRIS tanpa membuka browser...")

        def done(result) -> None:
            if self._disposed:
                return
            self._set_busy(False)
            if not result.success:
                self.validation_summary.show_lines(
                    [result.error or "Validation gagal."]
                )
                self.validation_summary.grid()
                return
            resolved, validation = result.value
            self._show_validation(validation)
            if not validation.valid or not run_after:
                return
            summary = (
                f"Workflow: {resolved.workflow}\n"
                f"Period: {resolved.period_start} - {resolved.period_end}\n"
                f"Source: {resolved.source_folder}\n"
                f"TXT: {validation.txt_count}\n"
                f"Run Controls: {len(validation.mappings)}\n"
                f"Profile: {resolved.recorder_profile}\n"
                f"Output: {resolved.output_root}\n\n"
                "Recorder profile akan menjalankan Upload, OK, Run, dan OK "
                "secara otomatis. Mulai job?"
            )
            if self.services.dialog_service.confirm("Mulai HRIS Upload", summary):
                self._start_run(resolved)

        self.services.task_runner.submit(
            lambda: self.services.hris_service.preflight(request), on_done=done
        )

    def _start_run(self, resolved) -> None:
        self._resolved = resolved
        self._cancellation = HRISCancellationToken()
        self._running = True
        self._set_busy(True, "HRIS job dimulai...")
        self.cancel_button.configure(state="normal")
        self.cancel_button.pack(side="left", padx=(8, 0))

        def work(report):
            return self.services.hris_service.run_job(
                resolved,
                cancellation=self._cancellation,
                progress=report,
                log=report,
                intervention=report,
            )

        def done(result) -> None:
            if self._disposed:
                return
            self._running = False
            self.cancel_button.configure(state="disabled")
            self.cancel_button.pack_forget()
            self._disable_intervention()
            self._set_busy(False)
            if result.success:
                self._last_result = result.value
                self._show_result(result.value)
            else:
                self.result_panel.grid()
                self.result_summary.show_lines(
                    ["FAILED", result.error or "Unexpected error"]
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
        if isinstance(event, HRISProgressEvent):
            message = event.message
            if event.total_files:
                message += f" | File {event.completed_files} dari {event.total_files}"
            self.progress.start(message)
        elif isinstance(event, HRISLogEvent):
            self._append_log(event)
        elif isinstance(event, HRISInterventionRequest):
            self._show_intervention(event)

    def _show_intervention(self, event: HRISInterventionRequest) -> None:
        self._disable_intervention()
        self._intervention_state = event.state
        self._set_intervention_status(event.message)
        self.intervention_file_var.set(
            f"File: {event.txt_file.name if event.txt_file else '-'}"
        )
        self.intervention_control_var.set(
            f"Run Control: {event.run_control_id or '-'}"
        )
        if event.state == HRISJobState.WAITING_FOR_LOGIN:
            self.login_continue_button.configure(state="normal")
        elif event.state == HRISJobState.WAITING_FOR_CHECKPOINT:
            self.upload_continue_button.configure(
                text="Lanjutkan",
                state="normal",
            )
            self.intervention_stop_button.configure(state="normal")
        elif event.state == HRISJobState.WAITING_FOR_VERIFICATION:
            self.upload_continue_button.configure(
                text="Sudah Submitted",
                state="normal",
            )
            self.upload_failed_button.configure(state="normal")
            self.verification_retry_button.configure(state="normal")
            self.intervention_stop_button.configure(state="normal")

    def confirm_login(self) -> None:
        if self._resolved:
            self.services.hris_service.confirm_login_complete(self._resolved.job_id)
            self.login_continue_button.configure(state="disabled")

    def confirm_upload(self) -> None:
        action = (
            "submitted"
            if self._intervention_state == HRISJobState.WAITING_FOR_VERIFICATION
            else "continue"
        )
        self.choose_intervention(action)

    def report_upload_failed(self) -> None:
        self.choose_intervention("failed")

    def choose_intervention(self, action: str) -> None:
        if self._resolved:
            self.services.hris_service.choose_intervention(
                self._resolved.job_id,
                action,
            )
            self._disable_intervention()

    def cancel(self) -> None:
        if not self._running or not self._resolved or not self._cancellation:
            return
        self.cancel_button.configure(state="disabled")
        self.services.task_runner.submit(
            lambda: self.services.hris_service.request_cancel(
                self._resolved, self._cancellation
            ),
            on_done=lambda _result: None,
            cancellable=False,
        )

    def _show_validation(self, value) -> None:
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        for item in value.mappings:
            self.mapping_tree.insert(
                "",
                "end",
                values=(
                    item.sequence,
                    item.run_control_id,
                    item.workflow,
                    item.mapping_status,
                ),
            )
        self._set_profile_status(
            value.profile.validation_status
            if value.profile
            else "Profile tidak tersedia."
        )
        self.validation_summary.show_lines(
            [
                f"Valid: {value.valid}",
                f"Workflow: {value.workflow}",
                f"Period: {value.period_start} - {value.period_end}",
                f"TXT / Mapping: {value.txt_count}",
                *value.warnings,
                *value.errors,
            ]
        )
        self.validation_summary.grid()

    def _set_profile_status(self, text: str) -> None:
        normalized = text.casefold()
        if normalized == "ready" or normalized.startswith("profile tersimpan"):
            style = "StatusReady.TLabel"
        elif normalized.startswith("kalibrasi berjalan"):
            style = "StatusRunning.TLabel"
        elif "gagal" in normalized or normalized == "error":
            style = "StatusError.TLabel"
        elif any(
            token in normalized
            for token in ("tidak tersedia", "not found", "mismatch")
        ):
            style = "StatusWarning.TLabel"
        else:
            style = "StatusInfo.TLabel"
        self.profile_status_var.set(text)
        self.profile_status_label.configure(style=style)

    def _set_intervention_status(self, text: str) -> None:
        self.intervention_status_var.set(text)
        self.intervention_status_label.configure(style="CompactStatus.TLabel")

    def _show_result(self, value) -> None:
        self.result_panel.grid()
        self.result_summary.show_lines(
            [
                f"Status: {'CANCELLED' if value.cancelled else 'COMPLETED' if value.success else 'FAILED'}",
                f"Job: {value.job_id}",
                f"Success: {sum(item.status == 'SUCCESS' for item in value.files)}",
                f"Failed: {sum(item.status != 'SUCCESS' for item in value.files)}",
                value.error_summary or "",
            ]
        )

    def _wait_for_calibration_navigation(self, message: str) -> None:
        confirmed = threading.Event()
        cancelled = {"value": False}

        def prompt() -> None:
            if not messagebox.askokcancel(
                "HRIS Calibration - Manual Navigation",
                f"{message}\n\nKlik OK hanya setelah halaman upload siap.",
                parent=self.winfo_toplevel(),
            ):
                cancelled["value"] = True
            confirmed.set()

        self.after(0, prompt)
        confirmed.wait()
        if cancelled["value"]:
            raise RuntimeError("Kalibrasi click profile dibatalkan.")

    def _capture_calibration_point(self, message: str) -> tuple[int, int]:
        """Capture the pointer with global F8 while Edge remains interactive."""
        completed = threading.Event()
        dialog_ready = threading.Event()
        result: dict[str, object] = {"cancelled": False}
        dialog_holder: dict[str, tk.Toplevel] = {}
        root = self.winfo_toplevel()

        def finish_capture() -> None:
            dialog = dialog_holder.get("dialog")
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()
            try:
                root.bell()
            except tk.TclError:
                pass
            completed.set()

        def close_dialog() -> None:
            dialog = dialog_holder.get("dialog")
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()

        def capture_hotkey() -> None:
            if completed.is_set():
                return
            import pyautogui

            position = pyautogui.position()
            result["coordinate"] = (int(position.x), int(position.y))
            self.after(0, finish_capture)

        def prompt() -> None:
            dialog = tk.Toplevel(root)
            dialog_holder["dialog"] = dialog
            dialog.title("HRIS Click Calibration")
            dialog.geometry(
                f"460x250+{max(10, dialog.winfo_screenwidth() - 480)}+40"
            )
            dialog.resizable(False, False)
            dialog.attributes("-topmost", True)

            ttk.Label(
                dialog,
                text=message,
                justify="left",
                wraplength=420,
                padding=(18, 18),
            ).pack(fill="both", expand=True)
            ttk.Label(
                dialog,
                text=(
                    "Arahkan pointer ke target di Edge,\n"
                    "lalu tekan F8 untuk REKAM."
                ),
                style="CompactTitle.TLabel",
                padding=(8, 8),
            ).pack()
            ttk.Button(
                dialog,
                text="Batal Kalibrasi",
                style="AttendanceDanger.TButton",
                command=lambda: cancel(),
            ).pack(pady=(0, 14))

            def cancel(_event: object | None = None) -> None:
                if completed.is_set():
                    return
                result["cancelled"] = True
                dialog.destroy()
                completed.set()

            dialog.bind("<Escape>", cancel)
            dialog.protocol("WM_DELETE_WINDOW", cancel)
            dialog_ready.set()

        self.after(0, prompt)
        dialog_ready.wait()
        listener = WindowsGlobalHotkey(capture_hotkey)
        try:
            listener.start()
            completed.wait()
        finally:
            listener.stop()
            if not completed.is_set():
                self.after(0, close_dialog)
        if result["cancelled"]:
            raise RuntimeError("Kalibrasi click profile dibatalkan.")
        coordinate = result.get("coordinate")
        if not isinstance(coordinate, tuple):
            raise RuntimeError("Koordinat kalibrasi tidak terekam.")
        return coordinate

    def show_active_configuration(self) -> None:
        status = self.services.storage_service.resolve_status()
        if not status.database_valid or status.database_path is None:
            self.services.dialog_service.warning("HRIS", "Database aktif belum tersedia.")
            return
        self.services.task_runner.submit(
            lambda: self.services.module_configuration_service.load_detail(
                status.database_path, "HRIS"
            ),
            on_done=lambda result: ModuleConfigurationDetailDialog(self, result.value)
            if result.success
            else self.services.dialog_service.warning("HRIS", result.error),
        )

    def browse_source(self) -> None:
        path = self.services.dialog_service.select_folder(title="Pilih Folder TXT HRIS")
        if path:
            self.source_var.set(str(path))
            self.refresh_source()

    def select_profile(self) -> None:
        path = self.services.dialog_service.select_file(
            title="Pilih Recorder Profile HRIS",
            filetypes=(("JSON", "*.json"),),
        )
        if not path:
            return
        if not self._data_root:
            self.services.dialog_service.warning("Profile", "Data Root belum tersedia.")
            return
        try:
            relative = path.resolve().relative_to(self._data_root.resolve())
        except ValueError:
            self.services.dialog_service.warning(
                "Profile", "Profile harus berada di DataRoot/recorder_profiles/hris."
            )
            return
        self.profile_var.set(str(relative))

    def browse_fallback(self) -> None:
        path = self.services.dialog_service.select_file(
            title="Pilih HRIS Legacy Workbook",
            filetypes=(("Excel", "*.xlsx"),),
        )
        if path:
            self.fallback_path_var.set(str(path))

    def _toggle_fallback(self) -> None:
        if self.fallback_var.get():
            self.fallback_frame.grid()
        else:
            self.fallback_path_var.set("")
            self.fallback_frame.grid_remove()

    def _apply_global_period_state(self) -> None:
        state = "readonly" if self.global_period_var.get() else "normal"
        self.start_entry.set_state(state)
        self.end_entry.set_state(state)

    def _disable_intervention(self) -> None:
        self.login_continue_button.configure(state="disabled")
        self.upload_continue_button.configure(state="disabled")
        self.upload_failed_button.configure(state="disabled")
        self.verification_retry_button.configure(state="disabled")
        self.intervention_stop_button.configure(state="disabled")

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.validate_button.configure(state="disabled" if busy else "normal")
        self.run_button.configure(state="disabled" if busy else "normal")
        self.calibrate_button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.start(message)
        elif not self._running:
            self.progress.stop()

    def _append_log(self, event: HRISLogEvent) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(
            "end", f"{event.timestamp} [{event.level}] [{event.stage}] {event.message}\n"
        )
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

    def _open(self, path, title: str) -> None:
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(title, "Path tidak tersedia.")

    def open_source_folder(self) -> None:
        raw = self.source_var.get().strip()
        self._open(Path(raw) if raw else None, "Open Source")

    def open_output_folder(self) -> None:
        self._open(
            self._last_result.output_folder if self._last_result else None,
            "Open Uploaded",
        )

    def open_process_log(self) -> None:
        self._open(
            self._last_result.process_log_path if self._last_result else None,
            "Open Log",
        )

    def open_profile_folder(self) -> None:
        self._open(
            self._data_root / "recorder_profiles" / "hris"
            if self._data_root
            else None,
            "Open Profile Folder",
        )

    def retry(self) -> None:
        if not self._running:
            self._last_result = None
            self.result_summary.show_lines(["Siap untuk job baru."])

    def return_settings(self) -> None:
        if not self._running and self.context.navigate:
            self.context.navigate("settings")

    def can_navigate_away(self) -> bool:
        return not self._running

    def dispose(self) -> None:
        self._disposed = True
        self.progress.stop()
        if self._cancellation:
            self._cancellation.request()
