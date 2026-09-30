"""Storage status, explicit initialization, relocation, and validation."""

from __future__ import annotations

from tkinter import ttk

from ui.dialogs.database_validation_dialog import DatabaseValidationDialog
from ui.pages.settings.common import SettingsSection
from ui.widgets import ResultSummary


class StorageSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        ttk.Label(self, text="Storage & Database", style="SectionHeader.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.result = ResultSummary(self)
        self.result.grid(row=1, column=0, sticky="ew", pady=10)
        buttons = ttk.Frame(self, style="OASK.TFrame")
        buttons.grid(row=2, column=0, sticky="w")
        actions = (
            ("Refresh Status", self.refresh),
            ("Initialize Data Location", self.initialize),
            ("Create/Initialize ATTENDANCE & OT", self.initialize_attendance_ot),
            ("Repair ATTENDANCE & OT", self.repair_attendance_ot),
            ("Change Data Location", self.relocate),
            ("Open Data Root", self.open_root),
            ("Open Database Folder", self.open_database),
            ("Validate Database", self.validate_database),
        )
        for index, (text, command) in enumerate(actions):
            button = ttk.Button(buttons, text=text, command=command)
            button.grid(row=index // 3, column=index % 3, padx=4, pady=4)
            self.page.register_action(button)

    def refresh(self) -> None:
        self.page.run_task(
            self.services.storage_service.resolve_status,
            on_success=self.show_status,
            message="Membaca status storage...",
        )

    def show_status(self, status) -> None:
        analytics_service = getattr(self.services, "attendance_ot_service", None)
        analytics = analytics_service.resolve_status() if analytics_service else None
        self.result.show_lines(
            [
                "CORE OAS-K DATABASE",
                f"Active Data Root: {status.data_root or '-'}",
                f"Active Database: {status.database_path or '-'}",
                f"Resolution: {status.resolution_status}",
                f"Database Exists: {status.database_exists}",
                f"Database Valid: {status.database_valid}",
                f"Schema: {status.schema_version or '-'}",
                f"Application: {status.application_version or '-'}",
                f"Registry: {status.registry_status}",
                f"Recorder Profiles: {status.recorder_profiles_folder or '-'}",
                f"Backup: {status.backup_folder or '-'}",
                f"Output: {status.output_folder or '-'}",
                f"Logs: {status.logs_folder or '-'}",
                f"Diagnostics: {status.diagnostics_folder or '-'}",
                "",
                "ATTENDANCE & OT DATABASE",
                f"Path: {analytics.database_path if analytics else '-'}",
                f"Status: {analytics.status if analytics else 'Service tidak tersedia'}",
                f"Size: {self._format_size(analytics.size_bytes) if analytics else '-'}",
                f"Schema Version: {analytics.schema_version if analytics and analytics.schema_version is not None else '-'}",
                "Last Initialization/Migration: "
                + (
                    analytics.last_initialization_or_migration
                    if analytics and analytics.last_initialization_or_migration
                    else "-"
                ),
                *(
                    [f"Analytics Error: {analytics.error}"]
                    if analytics and analytics.error
                    else []
                ),
                *(f"Warning: {item}" for item in status.warnings),
                *(f"Error: {item}" for item in status.errors),
            ]
        )

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        if size_bytes is None:
            return "-"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.1f} MB"
        return f"{size_bytes / 1024**3:.2f} GB"

    def initialize_attendance_ot(self) -> None:
        service = getattr(self.services, "attendance_ot_service", None)
        if service is None:
            self.services.dialog_service.warning(
                "ATTENDANCE & OT", "Analytics storage service tidak tersedia."
            )
            return

        def done(_status) -> None:
            self.show_status(self.services.storage_service.resolve_status())
            self.services.dialog_service.info(
                "ATTENDANCE & OT", "Database analytics siap digunakan."
            )

        self.page.run_task(
            service.initialize,
            on_success=done,
            message="Menginisialisasi database ATTENDANCE & OT...",
            destructive=True,
            cancellable=False,
        )

    def repair_attendance_ot(self) -> None:
        service = getattr(self.services, "attendance_ot_service", None)
        if service is None:
            return
        if not self.services.dialog_service.confirm(
            "Repair ATTENDANCE & OT",
            "Repair hanya untuk interrupted SQLite transaction. Salinan database "
            "dan journal dibuat sebelum recovery. Lanjutkan?",
        ):
            return

        def done(result) -> None:
            self.show_status(self.services.storage_service.resolve_status())
            self.services.dialog_service.info(
                "Repair ATTENDANCE & OT",
                "Recovery selesai dan database tervalidasi.\n\n"
                f"Pre-recovery copy: {result['pre_recovery_copy']}\n"
                f"Verified backup: {result['verified_backup']}",
            )

        self.page.run_task(
            service.repair_interrupted_transaction,
            on_success=done,
            message="Memulihkan interrupted analytics transaction...",
            destructive=True,
            cancellable=False,
        )

    def initialize(self) -> None:
        target = self.services.dialog_service.select_folder(
            title="Pilih Data Root untuk diinisialisasi"
        )
        if target is None:
            return
        structure = (
            f"{target}\n"
            "database, recorder_profiles/hris, backup, output, logs, diagnostics"
        )
        if not self.services.dialog_service.confirm(
            "Initialize Data Location",
            "Struktur berikut akan dibuat setelah konfirmasi:\n" + structure,
        ):
            return
        write_registry = self.services.dialog_service.confirm(
            "Konfirmasi Registry",
            "Simpan Data Root ini ke Registry HKCU setelah database valid?",
        )
        self.page.run_task(
            lambda: self.services.storage_service.initialize(
                target, write_registry=write_registry
            ),
            on_success=lambda result: (
                self.show_status(self.services.storage_service.resolve_status()),
                self.services.dialog_service.info(
                    "Initialize Data Location",
                    "Berhasil." if result.success else "\n".join(result.errors),
                ),
            ),
            message="Menginisialisasi Data Root...",
            destructive=True,
            cancellable=False,
        )

    def relocate(self) -> None:
        source = self.active_data_root()
        target = self.services.dialog_service.select_folder(
            title="Pilih target Data Root"
        )
        if target is None:
            return
        if not self.services.dialog_service.confirm(
            "Change Data Location",
            "Database dan recorder profiles akan disalin. Output dan logs "
            "tidak disalin. Source lama tidak akan dihapus.",
        ):
            return
        self.page.run_task(
            lambda: self.services.storage_service.relocate_to(
                source,
                target,
                copy_recorder_profiles=True,
                copy_output=False,
                copy_logs=False,
            ),
            on_success=lambda result: self.services.dialog_service.info(
                "Change Data Location",
                "Berhasil." if result.success else "\n".join(result.errors),
            ),
            message="Menyalin Data Root...",
            destructive=True,
            cancellable=False,
        )

    def validate_database(self) -> None:
        database = self._require_active_database("Validate Database")
        if database is None:
            return
        self.page.run_task(
            lambda: self.services.storage_service.validate_database(database),
            on_success=lambda result: DatabaseValidationDialog(self, result),
            message="Memvalidasi database...",
        )

    def open_root(self) -> None:
        root = self._require_active_data_root("Open Data Root")
        if root is None:
            return
        if not self.services.file_system_service.open_folder(root):
            self.services.dialog_service.warning("Open Folder", str(root))

    def open_database(self) -> None:
        database = self._require_active_database("Open Database Folder")
        if database is None:
            return
        if not self.services.file_system_service.open_folder(database.parent):
            self.services.dialog_service.warning("Open Folder", str(database.parent))

    def _require_active_database(self, title: str):
        try:
            return self.active_database()
        except Exception as exc:
            self.services.dialog_service.warning(
                title,
                (
                    f"{exc}\n\n"
                    "Klik Refresh Status atau Initialize Data Location dulu."
                ),
            )
            return None

    def _require_active_data_root(self, title: str):
        try:
            return self.active_data_root()
        except Exception as exc:
            self.services.dialog_service.warning(
                title,
                (
                    f"{exc}\n\n"
                    "Klik Refresh Status atau Initialize Data Location dulu."
                ),
            )
            return None
