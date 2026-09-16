"""Explicit Backup & Recovery actions."""

from __future__ import annotations

from tkinter import ttk

from ui.dialogs.candidate_validation_dialog import CandidateValidationDialog
from ui.pages.settings.common import SettingsSection
from ui.widgets import ResultSummary


class RecoverySection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        ttk.Label(self, text="Backup & Recovery", style="SectionHeader.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self,
            text=(
                "Semua operasi pemulihan bersifat manual. Database aktif "
                "dibackup sebelum Restore, Import Existing Database, atau Reset."
            ),
            style="SectionHeader.TLabel",
            wraplength=800,
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))
        self.result = ResultSummary(self)
        self.result.grid(row=2, column=0, sticky="ew")
        actions = (
            ("Backup Database", self.backup_database),
            ("Backup Application Data", self.backup_application_data),
            ("Restore from Backup", self.restore),
            ("Import Existing Database", self.import_database),
            ("Reset to Default", self.reset),
            ("Recovery Status", self.recovery_status),
        )
        buttons = ttk.Frame(self, style="OASK.TFrame")
        buttons.grid(row=3, column=0, sticky="w", pady=8)
        for index, (text, command) in enumerate(actions):
            button = ttk.Button(buttons, text=text, command=command)
            button.grid(row=index // 3, column=index % 3, padx=4, pady=4)
            self.page.register_action(button)

    def backup_database(self) -> None:
        root = self.active_data_root()
        self.page.run_task(
            lambda: self.services.recovery_service.backup_database(root),
            on_success=lambda result: self.result.show_lines(
                [
                    f"Success: {result.success}",
                    f"Backup: {result.backup_path or '-'}",
                    f"SHA-256: {result.sha256 or '-'}",
                    f"Size: {result.file_size}",
                    *(result.errors or ()),
                ]
            ),
            message="Backup Database...",
            cancellable=False,
        )

    def backup_application_data(self) -> None:
        root = self.active_data_root()
        include_logs = self.services.dialog_service.confirm(
            "Backup Application Data",
            "Sertakan logs? Recorder Profiles selalu disertakan. "
            "Output tidak disertakan.",
        )
        include_diagnostics = self.services.dialog_service.confirm(
            "Backup Application Data",
            "Sertakan diagnostics?",
        )
        self.page.run_task(
            lambda: self.services.recovery_service.backup_application_data(
                root,
                include_logs=include_logs,
                include_diagnostics=include_diagnostics,
            ),
            on_success=lambda result: self.result.show_lines(
                [
                    f"Success: {result.success}",
                    f"Archive: {result.backup_path or '-'}",
                    f"SHA-256: {result.sha256 or '-'}",
                    *(result.errors or ()),
                ]
            ),
            message="Backup Application Data...",
            cancellable=False,
        )

    def restore(self) -> None:
        source = self.services.dialog_service.select_file(
            title="Pilih backup database atau application data",
            filetypes=(("Database/ZIP", "*.db *.zip"),),
        )
        if source is None:
            return
        if source.suffix.casefold() == ".db":
            self.page.run_task(
                lambda: self.services.recovery_service.validate_candidate(source),
                on_success=lambda candidate: self._confirm_restore(source, candidate),
                message="Memvalidasi candidate restore...",
            )
            return
        self._confirm_restore(source, None)

    def _confirm_restore(self, source, candidate) -> None:
        if candidate is not None:
            CandidateValidationDialog(self, candidate)
            if not candidate.can_activate:
                return
        if not self.services.dialog_service.confirm(
            "Restore from Backup",
            "Database aktif akan dibackup terlebih dahulu. "
            "Saya memahami proses restore.",
        ):
            return
        root = self.active_data_root()
        self.page.run_task(
            lambda: self.services.recovery_service.restore(
                source,
                root,
                confirmed=True,
                write_registry=False,
            ),
            on_success=self._show_recovery_result,
            message="Restore from Backup...",
            destructive=True,
            cancellable=False,
        )

    def import_database(self) -> None:
        source = self.services.dialog_service.select_file(
            title="Pilih Existing Database",
            filetypes=(("SQLite Database", "*.db"),),
        )
        if source is None:
            return
        self.page.run_task(
            lambda: self.services.recovery_service.validate_candidate(source),
            on_success=lambda candidate: self._confirm_import(source, candidate),
            message="Memvalidasi Existing Database...",
        )

    def _confirm_import(self, source, candidate) -> None:
        CandidateValidationDialog(self, candidate)
        if not candidate.can_activate:
            return
        if not self.services.dialog_service.confirm(
            "Import Existing Database",
            "Source akan disalin ke Data Root aktif, tidak digunakan langsung, "
            "dan tidak dihapus.",
        ):
            return
        root = self.active_data_root()
        self.page.run_task(
            lambda: self.services.recovery_service.import_database(
                source,
                root,
                confirmed=True,
                write_registry=False,
            ),
            on_success=self._show_recovery_result,
            message="Import Existing Database...",
            destructive=True,
            cancellable=False,
        )

    def reset(self) -> None:
        if not self.services.dialog_service.typed_confirm(
            "Reset to Default",
            "Database baru schema v1 akan dibuat. Ketik RESET untuk melanjutkan.",
            "RESET",
        ):
            return
        if not self.services.dialog_service.confirm(
            "Konfirmasi Reset Kedua",
            "Global settings dan konfigurasi aktif akan kosong. Lanjutkan?",
        ):
            return
        root = self.active_data_root()
        self.page.run_task(
            lambda: self.services.recovery_service.reset(
                root,
                typed_value="RESET",
                confirmed=True,
                write_registry=False,
            ),
            on_success=self._show_recovery_result,
            message="Reset to Default...",
            destructive=True,
            cancellable=False,
        )

    def recovery_status(self) -> None:
        status = self.active_status()
        lines = [
            f"Storage state: {status.resolution_status}",
            f"Database valid: {status.database_valid}",
            "Tidak ada tindakan otomatis.",
            "Pilihan manual: Restore from Backup, Import Existing Database, "
            "Reset to Default, atau Select Data Root.",
        ]
        self.result.show_lines(lines)

    def _show_recovery_result(self, result) -> None:
        self.result.show_lines(
            [
                f"Success: {result.success}",
                f"Active Database: {result.active_database}",
                f"Pre-operation Backup: {result.pre_operation_backup or '-'}",
                f"Rollback: {result.rolled_back}",
                *(result.warnings or ()),
                *(result.errors or ()),
            ]
        )
