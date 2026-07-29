"""Compact Utilities landing and operational workspaces."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from ui.constants import COMPACT_LOG_BACKGROUND, LOG_FONT, LOG_TEXT
from ui.icon_manager import IconManager
from ui.pages.base_page import BasePage
from ui.utilities_models import (
    AttachmentConsolidationCancellationToken,
    AttachmentConsolidationLogEvent,
    AttachmentConsolidationProgressEvent,
    AttachmentConsolidationRunRequest,
    ComparisonCancellationToken,
    ComparisonLogEvent,
    ComparisonProgressEvent,
    ComparisonRunRequest,
    UtilitiesFeature,
)
from ui.widgets import CompactProgress, DateEntry, ResultSummary
from ui.widgets import OptionChip, SegmentedChoice


class UtilitiesPage(BasePage):
    page_id = "utilities"
    title = "Utilities"
    subtitle = "Alat bantu perbandingan dan konsolidasi data."
    icon_name = "utilities.ico"

    def __init__(self, parent, context) -> None:
        self._busy = False
        self._running = False
        self._disposed = False
        self._feature = None
        self._resolved = None
        self._validation = None
        self._cancellation = None
        self._last_result = None
        self._run_icon = None
        self._open_folder_icon = None
        super().__init__(parent, context)
        self.configure(padding=(16, 10))

    def build_content(self) -> None:
        self.services = self.context.app_services
        self.host = ttk.Frame(self, style="OASK.TFrame")
        self.host.grid(row=1, column=0, sticky="nsew")
        self.host.columnconfigure(0, weight=1)
        self.host.rowconfigure(0, weight=1)
        self._build_landing()
        self._build_workspace()
        self.show_landing()

    def _build_landing(self) -> None:
        self.landing = ttk.Frame(self.host, style="OASK.TFrame")
        self.landing.columnconfigure((0, 1), weight=1, uniform="utilities")
        summaries = self.services.utilities_service.landing_summaries()
        for column, summary in enumerate(summaries):
            panel = ttk.Frame(
                self.landing, style="CompactPanel.TFrame", padding=(14, 12)
            )
            panel.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0, 8) if column == 0 else (8, 0),
            )
            panel.columnconfigure(0, weight=1)
            ttk.Label(panel, text=summary.title, style="CompactTitle.TLabel").grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(
                panel,
                text=summary.description,
                style="CompactText.TLabel",
                wraplength=430,
                justify="left",
            ).grid(row=1, column=0, sticky="w", pady=(6, 8))
            ttk.Label(panel, text=summary.status, style="CompactStatus.TLabel").grid(
                row=2, column=0, sticky="w"
            )
            ttk.Button(
                panel,
                text=f"Buka {summary.title}",
                style="AttendancePrimary.TButton",
                command=lambda feature=summary.feature: self.open_feature(feature),
            ).grid(row=3, column=0, sticky="w", pady=(10, 0))

    def _build_workspace(self) -> None:
        self.workspace = ttk.Frame(self.host, style="OASK.TFrame")
        self.workspace.columnconfigure(0, weight=1)
        self.workspace.rowconfigure(5, weight=1)

        self.workflow_var = tk.StringVar(value="HO")
        self.source_a_var = tk.StringVar()
        self.source_b_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.global_output_var = tk.BooleanVar(value=True)
        self.global_period_var = tk.BooleanVar(value=True)
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="EXCEL")
        self.subfolders_var = tk.BooleanVar(value=True)
        self.advanced_var = tk.BooleanVar(value=False)
        self.max_lines_var = tk.StringVar()
        self.config_status_var = tk.StringVar(value="Konfigurasi: Belum dimuat")
        self.source_status_var = tk.StringVar(value="Source: Belum dipilih")
        self.validation_status_var = tk.StringVar(value="Belum diperiksa")

        self._build_workspace_bar()
        self._build_configuration_strip()
        self._build_input_panel()
        self._build_action_row()
        self._build_progress()
        self._build_log()
        self._build_result()
        self._build_advanced()

    def _build_workspace_bar(self) -> None:
        bar = ttk.Frame(self.workspace, style="OASK.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(
            bar, text="< Utilities", style="Attendance.TButton", command=self.show_landing
        ).pack(side="left")
        self.workspace_title = ttk.Label(bar, text="", style="SectionHeader.TLabel")
        self.workspace_title.pack(side="left", padx=(10, 0))

    def _build_configuration_strip(self) -> None:
        strip = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(12, 8))
        strip.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        strip.columnconfigure(0, weight=1)
        ttk.Label(
            strip, textvariable=self.config_status_var, style="CompactTitle.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            strip, textvariable=self.source_status_var, style="CompactText.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        actions = ttk.Frame(strip, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(
            actions,
            text="Buka Settings",
            style="Attendance.TButton",
            command=self.open_settings,
        ).pack(side="left")
        ttk.Button(
            actions, text="Refresh", style="Attendance.TButton", command=self._load_defaults
        ).pack(side="left", padx=(6, 0))

    def _build_input_panel(self) -> None:
        panel = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(12, 10))
        panel.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=4)
        panel.columnconfigure(1, weight=3)
        panel.columnconfigure(2, weight=3)

        source = ttk.Frame(panel, style="CompactBody.TFrame")
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        source.columnconfigure(1, weight=1)
        self.source_a_label = ttk.Label(
            source, text="Attendance Source", style="CompactTitle.TLabel"
        )
        self.source_a_label.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Entry(source, textvariable=self.source_a_var, style="Modern.TEntry").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0)
        )
        ttk.Button(
            source,
            text="Browse",
            style="Attendance.TButton",
            command=lambda: self._browse(self.source_a_var),
        ).grid(row=1, column=2, padx=(6, 0), pady=(5, 0))
        self.source_b_label = ttk.Label(
            source, text="Outlook Revisi Source", style="CompactText.TLabel"
        )
        self.source_b_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(7, 2))
        self.source_b_entry = ttk.Entry(
            source, textvariable=self.source_b_var, style="Modern.TEntry"
        )
        self.source_b_entry.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.source_b_browse = ttk.Button(
            source,
            text="Browse",
            style="Attendance.TButton",
            command=lambda: self._browse(self.source_b_var),
        )
        self.source_b_browse.grid(row=3, column=2, padx=(6, 0))

        period = ttk.Frame(panel, style="CompactBody.TFrame")
        period.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        period.columnconfigure((0, 1), weight=1)
        ttk.Label(period, text="Periode & Workflow", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        OptionChip(
            period,
            text="Gunakan periode dari Settings",
            variable=self.global_period_var,
            command=self._apply_global_state,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 2))
        self.start_entry = DateEntry(period, textvariable=self.start_var, width=11)
        self.start_entry.grid(row=2, column=0, sticky="ew")
        self.end_entry = DateEntry(period, textvariable=self.end_var, width=11)
        self.end_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0))
        workflow = ttk.Frame(period, style="CompactBody.TFrame")
        workflow.grid(row=3, column=0, columnspan=2, sticky="w", pady=(7, 0))
        SegmentedChoice(
            workflow,
            variable=self.workflow_var,
            choices=(("HO", "HO"), ("BRANCH", "BRANCH")),
        ).pack(anchor="w")

        output = ttk.Frame(panel, style="CompactBody.TFrame")
        output.grid(row=0, column=2, sticky="nsew")
        output.columnconfigure(0, weight=1)
        ttk.Label(output, text="Output & Options", style="CompactTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        OptionChip(
            output,
            text="Gunakan output dari Settings",
            variable=self.global_output_var,
            command=self._apply_global_state,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 2))
        self.output_entry = ttk.Entry(
            output, textvariable=self.output_var, style="Modern.TEntry"
        )
        self.output_entry.grid(row=2, column=0, sticky="ew")
        self.output_browse = ttk.Button(
            output,
            text="Browse",
            style="Attendance.TButton",
            command=lambda: self._browse(self.output_var),
        )
        self.output_browse.grid(row=2, column=1, padx=(6, 0))
        self.attachment_options = ttk.Frame(output, style="CompactBody.TFrame")
        self.attachment_options.grid(row=3, column=0, columnspan=2, sticky="w", pady=(7, 0))
        SegmentedChoice(
            self.attachment_options,
            variable=self.mode_var,
            choices=(("EXCEL", "EXCEL"), ("TXT", "TXT")),
        ).pack(side="left")
        OptionChip(
            self.attachment_options, text="Subfolder", variable=self.subfolders_var
        ).pack(side="left", padx=(8, 0))

    def _build_action_row(self) -> None:
        row = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(12, 7))
        row.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text="Validasi:", style="CompactText.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.validation_status_label = ttk.Label(
            row,
            textvariable=self.validation_status_var,
            style="StatusInfo.TLabel",
        )
        self.validation_status_label.grid(row=0, column=0, sticky="w", padx=(58, 0))
        self.validation_summary = ResultSummary(row, wraplength=700)
        self.validation_summary.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.validation_summary.grid_remove()
        actions = ttk.Frame(row, style="CompactBody.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.validate_button = ttk.Button(
            actions, text="Periksa Data", style="Attendance.TButton", command=self.validate
        )
        self.validate_button.pack(side="left")
        self.run_button = ttk.Button(
            actions, text="Start", style="AttendancePrimary.TButton", command=self.run
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
            state="disabled",
            style="AttendanceDanger.TButton",
            command=self.cancel,
        )
        self.cancel_button.pack(side="left", padx=(8, 0), anchor="n")
        self.cancel_button.pack_forget()

    def _build_progress(self) -> None:
        panel = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(12, 6))
        panel.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        panel.columnconfigure(0, weight=1)
        self.progress = CompactProgress(panel)
        self.progress.grid(row=0, column=0, sticky="ew")

    def _build_log(self) -> None:
        panel = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(10, 8))
        panel.grid(row=5, column=0, sticky="nsew", pady=(0, 8))
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
        ttk.Button(actions, text="Salin", style="Attendance.TButton", command=self.copy_log).pack(side="left")
        ttk.Button(actions, text="Bersihkan", style="Attendance.TButton", command=self.clear_log).pack(side="left", padx=(6, 0))
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
            self.workspace, style="CompactPanel.TFrame", padding=(10, 8)
        )
        self.result_panel.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.result_panel.columnconfigure(0, weight=1)
        self.result_summary = ResultSummary(self.result_panel, wraplength=720)
        self.result_summary.grid(row=0, column=0, sticky="ew")
        recovery = ttk.Frame(self.result_panel, style="CompactBody.TFrame")
        recovery.grid(row=0, column=1, sticky="e", padx=(10, 0))
        for text, command in (
            ("Buka Output", self.open_output),
            ("Buka Report", self.open_report),
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
        section = ttk.Frame(self.workspace, style="CompactPanel.TFrame", padding=(10, 6))
        section.grid(row=7, column=0, sticky="ew")
        ttk.Checkbutton(
            section,
            text="Advanced / Per-run Override",
            variable=self.advanced_var,
            command=self._toggle_advanced,
        ).grid(row=0, column=0, sticky="w")
        self.advanced = ttk.Frame(section, style="CompactBody.TFrame")
        self.advanced.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Label(self.advanced, text="TXT Max Lines", style="CompactText.TLabel").pack(
            side="left"
        )
        ttk.Entry(self.advanced, textvariable=self.max_lines_var, width=12).pack(
            side="left", padx=(6, 0)
        )
        self.advanced.grid_remove()

    def open_feature(self, feature: UtilitiesFeature) -> None:
        if self._running:
            return
        self._feature = feature
        title = (
            "Comparison Result"
            if feature == UtilitiesFeature.COMPARISON_RESULT
            else "Attachment Consolidation"
        )
        self.workspace_title.configure(text=title)
        is_comparison = feature == UtilitiesFeature.COMPARISON_RESULT
        if is_comparison:
            self.source_a_label.configure(text="Attendance Source")
            self.source_b_label.grid()
            self.source_b_entry.grid()
            self.source_b_browse.grid()
            self.attachment_options.grid_remove()
        else:
            self.source_a_label.configure(text="Attachment Source")
            self.source_b_label.grid_remove()
            self.source_b_entry.grid_remove()
            self.source_b_browse.grid_remove()
            self.attachment_options.grid()
        self.landing.grid_remove()
        self.workspace.grid(row=0, column=0, sticky="nsew")
        self._load_defaults()

    def show_landing(self) -> None:
        if self._running:
            return
        self.workspace.grid_remove()
        self.landing.grid(row=0, column=0, sticky="nsew")

    def _load_defaults(self) -> None:
        service = self._service()
        self._set_busy(True, "Memuat konfigurasi...")
        self.services.task_runner.submit(
            service.load_defaults, on_done=self._defaults_done
        )

    def _defaults_done(self, result) -> None:
        if self._disposed:
            return
        self._set_busy(False)
        if not result.success:
            self.config_status_var.set(result.error or "Configuration unavailable")
            return
        value = result.value
        if value.output_root:
            self.output_var.set(str(value.output_root))
        if value.period_start:
            self.start_entry.set_iso(value.period_start)
        if value.period_end:
            self.end_entry.set_iso(value.period_end)
        if self._feature == UtilitiesFeature.COMPARISON_RESULT:
            self.global_output_var.set(value.comparison_use_global_output)
            self.global_period_var.set(value.comparison_use_global_period)
            updated = value.comparison_updated_at
            self.config_status_var.set(
                f"Konfigurasi: Comparison Result - Updated: {updated or '-'}"
            )
            self.source_status_var.set("Source: Attendance + Outlook Revisi")
        else:
            self.global_output_var.set(value.attachment_use_global_output)
            self.max_lines_var.set(str(value.attachment_txt_max_lines))
            updated = value.attachment_updated_at
            self.config_status_var.set(
                f"Konfigurasi: Attachment Consolidation - Updated: {updated or '-'}"
            )
            self.source_status_var.set(
                f"Source: Attachment folder - TXT max {value.attachment_txt_max_lines}"
            )
        if value.warning:
            self.validation_summary.show_lines([value.warning])
            self.validation_summary.grid()
        self._apply_global_state()

    def _service(self):
        if self._feature == UtilitiesFeature.COMPARISON_RESULT:
            return self.services.comparison_result_service
        return self.services.attachment_consolidation_service

    def _request(self):
        output = (
            Path(self.output_var.get().strip())
            if self.output_var.get().strip()
            else None
        )
        if self._feature == UtilitiesFeature.COMPARISON_RESULT:
            return ComparisonRunRequest(
                Path(self.source_a_var.get().strip()),
                Path(self.source_b_var.get().strip()),
                self.workflow_var.get(),
                self.global_period_var.get(),
                self.start_entry.get_iso(),
                self.end_entry.get_iso(),
                self.global_output_var.get(),
                output,
            )
        override = None
        if self.advanced_var.get() and self.max_lines_var.get().strip():
            override = int(self.max_lines_var.get())
        return AttachmentConsolidationRunRequest(
            Path(self.source_a_var.get().strip()),
            self.workflow_var.get(),
            self.mode_var.get(),
            self.subfolders_var.get(),
            self.global_output_var.get(),
            output,
            override,
        )

    def validate(self) -> None:
        self._preflight(False)

    def run(self) -> None:
        self._preflight(True)

    def _preflight(self, run_after: bool) -> None:
        if self._busy:
            return
        try:
            request = self._request()
        except (ValueError, TypeError) as exc:
            self.validation_summary.show_lines([str(exc)])
            self.validation_summary.grid()
            self._set_validation_status("Perlu perhatian", "StatusWarning.TLabel")
            return
        token = (
            ComparisonCancellationToken()
            if self._feature == UtilitiesFeature.COMPARISON_RESULT
            else AttachmentConsolidationCancellationToken()
        )
        self._set_busy(True, "Read-only validation...")
        self.services.task_runner.submit(
            lambda: self._service().preflight(request, cancellation=token),
            on_done=lambda result: self._preflight_done(result, run_after),
        )

    def _preflight_done(self, task, run_after: bool) -> None:
        if self._disposed:
            return
        self._set_busy(False)
        if not task.success:
            self.validation_summary.show_lines([task.error or "Validation failed"])
            self.validation_summary.grid()
            self._set_validation_status("Perlu perhatian", "StatusWarning.TLabel")
            return
        resolved, validation = task.value
        self._resolved, self._validation = resolved, validation
        lines = [f"Valid: {validation.valid}"]
        for name in (
            "attendance_reports",
            "outlook_reports",
            "total_files",
            "processable_files",
            "invalid_files",
            "duplicate_candidates",
            "subfolder_count",
        ):
            if hasattr(validation, name):
                lines.append(
                    f"{name.replace('_', ' ').title()}: {getattr(validation, name)}"
                )
        lines.extend(validation.warnings)
        lines.extend(validation.errors)
        self.validation_summary.show_lines(lines)
        self.validation_summary.grid()
        self._set_validation_status(
            "Siap" if validation.valid else "Perlu perhatian"
        )
        if (
            run_after
            and validation.valid
            and self.services.dialog_service.confirm(
                "Run Utilities Job",
                f"Workflow: {resolved.workflow}\n"
                f"Output: {resolved.output_root}\n\nMulai job baru?",
            )
        ):
            self._start_run()

    def _start_run(self) -> None:
        self._cancellation = (
            ComparisonCancellationToken()
            if self._feature == UtilitiesFeature.COMPARISON_RESULT
            else AttachmentConsolidationCancellationToken()
        )
        self._running = True
        self.cancel_button.configure(state="normal")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self._set_validation_status("Sedang berjalan", "StatusRunning.TLabel")
        self._set_busy(True, "Job running...")

        def work(report):
            return self._service().run_job(
                self._resolved,
                self._validation,
                cancellation=self._cancellation,
                progress=report,
                log=report,
            )

        self.services.task_runner.submit_reporting(
            work,
            on_done=self._run_done,
            on_progress=self._stream_event,
            cancellable=False,
        )

    def _run_done(self, task) -> None:
        if self._disposed:
            return
        self._running = False
        self.cancel_button.configure(state="disabled")
        self.cancel_button.pack_forget()
        self._set_busy(False)
        self.result_panel.grid()
        if not task.success:
            self.result_summary.show_lines(["FAILED", task.error or "Unexpected error"])
            self._set_validation_status("Gagal", "StatusError.TLabel")
            return
        self._last_result = task.value
        value = task.value
        lines = [
            f"Status: {'CANCELLED' if value.cancelled else 'SUCCESS' if value.success else 'FAILED'}",
            f"Job ID: {value.job_id}",
            f"Output Files: {len(value.outputs)}",
            f"Warnings: {value.warning_count}",
            f"Output: {value.output_folder or '-'}",
        ]
        for name in (
            "total_records",
            "attention_count",
            "conflict_count",
            "invalid_count",
            "files_scanned",
            "files_accepted",
            "files_rejected",
            "duplicates",
            "output_txt_count",
            "report_count",
        ):
            if hasattr(value, name):
                lines.append(
                    f"{name.replace('_', ' ').title()}: {getattr(value, name)}"
                )
        if getattr(value, "status_breakdown", ()):
            lines.extend(f"{status}: {count}" for status, count in value.status_breakdown)
        try:
            duration = max(
                0.0,
                (
                    datetime.fromisoformat(value.ended_at)
                    - datetime.fromisoformat(value.started_at)
                ).total_seconds(),
            )
            lines.append(f"Duration: {duration:.2f} seconds")
        except ValueError:
            pass
        if value.error_summary:
            lines.append(value.error_summary)
        self.result_summary.show_lines(lines)
        status_text, status_style = (
            ("Dibatalkan", "StatusInfo.TLabel")
            if value.cancelled
            else ("Berhasil dengan peringatan", "StatusWarning.TLabel")
            if value.success and value.warning_count
            else ("Berhasil", "StatusReady.TLabel")
            if value.success
            else ("Gagal", "StatusError.TLabel")
        )
        self._set_validation_status(status_text, status_style)

    def _set_validation_status(self, text: str, style: str | None = None) -> None:
        if style is None:
            normalized = text.casefold()
            if normalized.startswith("siap") or normalized.startswith("berhasil"):
                style = "StatusReady.TLabel"
            elif normalized.startswith("gagal"):
                style = "StatusError.TLabel"
            elif normalized.startswith("perlu perhatian"):
                style = "StatusWarning.TLabel"
            elif normalized.startswith("sedang berjalan"):
                style = "StatusRunning.TLabel"
            elif normalized.startswith(("dibatalkan", "belum diperiksa")):
                style = "StatusInfo.TLabel"
            else:
                style = "CompactStatus.TLabel"
        self.validation_status_var.set(text)
        self.validation_status_label.configure(style=style)

    def _stream_event(self, event) -> None:
        if isinstance(
            event, (ComparisonProgressEvent, AttachmentConsolidationProgressEvent)
        ):
            self.progress.start(event.message)
        elif isinstance(event, (ComparisonLogEvent, AttachmentConsolidationLogEvent)):
            self._append_log(event)

    def cancel(self) -> None:
        if not self._running or self._cancellation is None:
            return
        self._cancellation.request()
        self.cancel_button.configure(state="disabled")
        self.progress.start("Cancellation requested; waiting for safe checkpoint...")
        self.services.task_runner.submit(
            lambda: self._service().request_cancellation(
                self._resolved, self._cancellation
            ),
            on_done=lambda _result: None,
            cancellable=False,
        )

    def _browse(self, variable: tk.StringVar) -> None:
        path = self.services.dialog_service.select_folder(title="Pilih Folder")
        if path:
            variable.set(str(path))

    def _toggle_advanced(self) -> None:
        if (
            self.advanced_var.get()
            and self._feature == UtilitiesFeature.ATTACHMENT_CONSOLIDATION
        ):
            self.advanced.grid()
        else:
            self.advanced.grid_remove()

    def _apply_global_state(self) -> None:
        self.output_entry.configure(
            state="readonly" if self.global_output_var.get() else "normal"
        )
        self.output_browse.configure(
            state="disabled" if self.global_output_var.get() else "normal"
        )
        self.start_entry.set_state(
            "readonly" if self.global_period_var.get() else "normal"
        )
        self.end_entry.set_state(
            "readonly" if self.global_period_var.get() else "normal"
        )

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.validate_button.configure(state=state)
        self.run_button.configure(state=state)
        if busy:
            self.progress.start(message)
        else:
            self.progress.stop()

    def _append_log(self, event) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(
            "end",
            f"{event.timestamp} [{event.level}] [{event.stage}] {event.message}\n",
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

    def open_output(self) -> None:
        path = self._last_result.output_folder if self._last_result else None
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning("Open Output", "Output belum tersedia.")

    def open_source(self) -> None:
        text = self.source_a_var.get().strip()
        path = Path(text) if text else None
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning("Open Source", "Source belum tersedia.")

    def _output_by_roles(self, *roles):
        if self._last_result is None:
            return None
        return next(
            (item.path for item in self._last_result.outputs if str(item.role) in roles),
            None,
        )

    def open_report(self) -> None:
        path = self._output_by_roles("COMPARISON_REPORT", "CONSOLIDATION_REPORT")
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning("Open Report", "Report belum tersedia.")

    def open_process_log(self) -> None:
        path = self._output_by_roles("PROCESS_LOG")
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Open Log", "Process log belum tersedia."
            )

    def retry(self) -> None:
        if not self._running:
            self._last_result = None
            self.result_summary.show_lines(["Siap untuk job baru."])

    def open_settings(self) -> None:
        if not self._running and self.context.navigate:
            self.context.navigate("settings")

    def can_navigate_away(self) -> bool:
        return not self._running

    def dispose(self) -> None:
        self._disposed = True
        if self._cancellation is not None:
            self._cancellation.request()
