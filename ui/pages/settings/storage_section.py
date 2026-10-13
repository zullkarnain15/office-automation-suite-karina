"""Storage status, explicit initialization, relocation, and validation."""

from __future__ import annotations

import calendar
import tkinter as tk
from tkinter import ttk

from ui.constants import MAIN_BACKGROUND
from ui.dialogs.attendance_ot_database_manager import (
    AttendanceOTDatabaseManagerDialog,
)
from ui.dialogs.database_validation_dialog import DatabaseValidationDialog
from ui.dialogs.operation_result_dialog import OperationResultDialog
from ui.pages.settings.common import SettingsSection
from ui.widgets import ResultSummary
from shared.attendance_ot.reporting import AnalyticsFilters


class StorageSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self.rowconfigure(0, weight=1)
        viewport = ttk.Frame(self, style="OASK.TFrame")
        viewport.grid(row=0, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(
            viewport,
            highlightthickness=0,
            background=MAIN_BACKGROUND,
        )
        scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self._canvas.yview,
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self._canvas, style="OASK.TFrame")
        window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind(
            "<Configure>",
            lambda _event: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )
        self._canvas.bind(
            "<Configure>",
            lambda event: self._canvas.itemconfigure(window, width=event.width),
        )
        self.content.columnconfigure(0, weight=1)

        ttk.Label(
            self.content,
            text="Storage & Database",
            style="SectionHeader.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.result = ResultSummary(self.content)
        self.result.grid(row=1, column=0, sticky="ew", pady=10)

        core_buttons = ttk.LabelFrame(
            self.content,
            text="Data Location & Core Database",
            padding=8,
            style="SettingsPanel.TLabelframe",
        )
        core_buttons.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        for column in range(2):
            core_buttons.columnconfigure(column, weight=1, uniform="storage_core")
        core_actions = (
            ("Refresh Status", self.refresh),
            ("Validate Database", self.validate_database),
            ("Initialize Data Location", self.initialize),
            ("Change Data Location", self.relocate),
            ("Open Data Root", self.open_root),
            ("Open Database Folder", self.open_database),
        )
        for index, (text, command) in enumerate(core_actions):
            button = ttk.Button(core_buttons, text=text, command=command)
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=4,
                pady=4,
            )
            self.page.register_action(button)

        attendance_buttons = ttk.LabelFrame(
            self.content,
            text="ATTENDANCE & OT Database",
            padding=8,
            style="SettingsPanel.TLabelframe",
        )
        attendance_buttons.grid(row=3, column=0, sticky="ew")
        for column in range(2):
            attendance_buttons.columnconfigure(
                column,
                weight=1,
                uniform="storage_attendance_ot",
            )
        attendance_actions = (
            ("Create/Initialize ATTENDANCE & OT", self.initialize_attendance_ot),
            ("Repair ATTENDANCE & OT", self.repair_attendance_ot),
        )
        for column, (text, command) in enumerate(attendance_actions):
            button = ttk.Button(attendance_buttons, text=text, command=command)
            button.grid(row=0, column=column, sticky="ew", padx=4, pady=4)
            self.page.register_action(button)

        maintenance_button = ttk.Button(
            attendance_buttons,
            text="Database Maintenance",
            command=self.attendance_ot_maintenance,
        )
        maintenance_button.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )
        self.page.register_action(maintenance_button)
        manage_button = ttk.Button(
            attendance_buttons,
            text="Kelola Database ATTENDANCE & OT",
            command=self.manage_attendance_ot_database,
        )
        manage_button.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.page.register_action(manage_button)
        self._bind_page_scrolling(viewport)

    def _bind_page_scrolling(self, widget) -> None:
        if isinstance(widget, (tk.Text, ttk.Combobox)):
            return
        if not getattr(widget, "_settings_scroll_bound", False):
            widget.bind("<MouseWheel>", self._scroll_page, add="+")
            widget.bind("<Button-4>", self._scroll_page, add="+")
            widget.bind("<Button-5>", self._scroll_page, add="+")
            widget._settings_scroll_bound = True
        for child in widget.winfo_children():
            self._bind_page_scrolling(child)

    def _scroll_page(self, event):
        if self._canvas.yview() == (0.0, 1.0):
            return None
        delta = getattr(event, "delta", 0)
        direction = -1 if getattr(event, "num", None) == 4 or delta > 0 else 1
        steps = max(1, abs(int(delta / 120))) if delta else 1
        self._canvas.yview_scroll(direction * steps * 3, "units")
        return "break"

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
        self._refresh_footer_storage_status()

    def _refresh_footer_storage_status(self) -> None:
        callback = self.page.context.refresh_storage_status
        if callback is not None:
            callback()

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
        def done(result) -> None:
            DatabaseValidationDialog(self, result)
            self._refresh_footer_storage_status()

        self.page.run_task(
            lambda: self.services.storage_service.validate_database(database),
            on_success=done,
            message="Memvalidasi database...",
        )

    def attendance_ot_maintenance(self) -> None:
        service = getattr(self.services, "attendance_ot_maintenance_service", None)
        if service is None:
            self.services.dialog_service.warning(
                "Database Maintenance",
                "Service maintenance ATTENDANCE & OT tidak tersedia.",
            )
            return

        def show(info) -> None:
            window = tk.Toplevel(self)
            window.title("ATTENDANCE & OT — Database Maintenance")
            window.transient(self.winfo_toplevel())
            window.configure(background=MAIN_BACKGROUND)
            window.columnconfigure(0, weight=1)
            details = "\n".join(
                f"{key.replace('_', ' ').title()}: {value if value is not None else '-'}"
                for key, value in info.items()
            )
            ttk.Label(
                window,
                text=(
                    details
                    + "\n\nPurge menghapus attendance pada periode terpilih. "
                    "Reset menghapus seluruh data analytics. Backup terverifikasi "
                    "dibuat sebelum data diubah."
                ),
                justify="left",
                wraplength=720,
            ).grid(row=0, column=0, sticky="ew", padx=16, pady=16)
            actions = ttk.Frame(window)
            actions.grid(row=1, column=0, pady=(0, 16))
            for label, command in (
                ("Purge Period/Year", lambda: self._preview_attendance_ot_cleanup("PURGE")),
                ("Reset Analytics Database", lambda: self._preview_attendance_ot_cleanup("RESET")),
                ("Compact / VACUUM", self._compact_attendance_ot_database),
            ):
                ttk.Button(actions, text=label, command=command).pack(
                    side="left", padx=4
                )

        self.page.run_task(
            service.info,
            on_success=show,
            message="Membaca status maintenance ATTENDANCE & OT...",
        )

    def _preview_attendance_ot_cleanup(self, operation: str) -> None:
        service = self.services.attendance_ot_maintenance_service
        low = high = ""
        if operation == "PURGE":
            value = self.services.dialog_service.prompt_text(
                "Purge Period/Year",
                "Hapus attendance untuk periode YYYY atau YYYY-MM:",
            )
            if value is None:
                return
            try:
                value = value.strip()
                AnalyticsFilters(period=value)
                if not value:
                    raise ValueError("Period wajib diisi.")
                year = int(value[:4])
                if len(value) == 4:
                    low, high = f"{year:04d}-01-01", f"{year:04d}-12-31"
                else:
                    month = int(value[5:7])
                    low, high = value + "-01", value + f"-{calendar.monthrange(year, month)[1]:02d}"
            except ValueError as exc:
                self.services.dialog_service.warning("Purge", str(exc))
                return

        def confirm(preview) -> None:
            if not self.services.dialog_service.typed_confirm(
                operation,
                preview.describe()
                + f"\n\nBackup dibuat dahulu. Ketik {operation} untuk menghapus data.",
                operation,
            ):
                return
            self.page.run_task(
                lambda: service.execute(preview, confirmation=operation),
                on_success=self._attendance_ot_cleanup_done,
                message=f"Menjalankan {operation} ATTENDANCE & OT...",
                destructive=True,
                cancellable=False,
            )

        self.page.run_task(
            lambda: service.preview(operation, low, high),
            on_success=confirm,
            message="Menyiapkan ringkasan penghapusan ATTENDANCE & OT...",
        )

    def _attendance_ot_cleanup_done(self, value) -> None:
        self.show_status(self.services.storage_service.resolve_status())
        self.services.dialog_service.info(
            "Database Maintenance",
            f"Deleted {value['deleted_records']:,} attendance records.\n"
            f"Backup: {value['backup']}",
        )

    def _compact_attendance_ot_database(self) -> None:
        service = self.services.attendance_ot_maintenance_service
        self.page.run_task(
            service.vacuum,
            on_success=lambda value: self.services.dialog_service.info(
                "VACUUM",
                f"Compact selesai. Size: {value['size_bytes']:,} bytes",
            ),
            message="Memadatkan database ATTENDANCE & OT...",
            destructive=True,
            cancellable=False,
        )

    def manage_attendance_ot_database(self) -> None:
        if self._attendance_ot_transfer_service() is None:
            return
        AttendanceOTDatabaseManagerDialog(
            self,
            on_validate=self.validate_attendance_ot_database_file,
            on_export=self.export_attendance_ot_database,
            on_import=self.import_attendance_ot_database,
        )

    def validate_attendance_ot_database_file(self) -> None:
        service = self._attendance_ot_transfer_service()
        if service is None:
            return
        candidate = self.services.dialog_service.select_file(
            title="Pilih Database ATTENDANCE & OT untuk Divalidasi",
            filetypes=(
                ("SQLite / Backup", "*.db *.bak"),
                ("Semua file", "*.*"),
            ),
        )
        if candidate is None:
            return
        self.page.run_task(
            lambda: service.validate_candidate(candidate),
            on_success=lambda result: OperationResultDialog(
                self,
                "Validasi Database ATTENDANCE & OT",
                result.lines(),
            ),
            message="Memvalidasi database ATTENDANCE & OT...",
        )

    def export_attendance_ot_database(self) -> None:
        service = self._attendance_ot_transfer_service()
        if service is None:
            return
        destination = self.services.dialog_service.save_file(
            title="Export Backup Database ATTENDANCE & OT",
            default_name="Attendance_OT_Backup.bak",
            filetypes=(
                ("SQLite Backup", "*.bak"),
                ("SQLite Database", "*.db"),
            ),
        )
        if destination is None:
            return

        def done(result) -> None:
            self.services.dialog_service.info(
                "Export Database ATTENDANCE & OT",
                "Backup portable selesai dan tervalidasi.\n\n"
                f"File: {result.destination}\n"
                f"Size: {self._format_size(result.size_bytes)}\n"
                f"SHA-256: {result.sha256}",
            )

        self.page.run_task(
            lambda: service.export_verified(destination),
            on_success=done,
            message="Membuat backup analytics terverifikasi...",
            destructive=True,
            cancellable=False,
        )

    def import_attendance_ot_database(self) -> None:
        service = self._attendance_ot_transfer_service()
        if service is None:
            return
        candidate = self.services.dialog_service.select_file(
            title="Pilih Database ATTENDANCE & OT untuk Diimport",
            filetypes=(
                ("SQLite / Backup", "*.db *.bak"),
                ("Semua file", "*.*"),
            ),
        )
        if candidate is None:
            return
        self.page.run_task(
            lambda: service.validate_candidate(candidate),
            on_success=lambda result: self._confirm_attendance_ot_import(
                candidate, result
            ),
            message="Memvalidasi kandidat database analytics...",
        )

    def _confirm_attendance_ot_import(self, candidate, validation) -> None:
        if not validation.is_valid:
            OperationResultDialog(
                self,
                "Database ATTENDANCE & OT Tidak Valid",
                validation.lines(),
            )
            return
        counts = "\n".join(
            f"- {name}: {count:,}" for name, count in validation.counts
        )
        warnings = "\n".join(f"- {item}" for item in validation.warnings)
        message = (
            "Database aktif akan diganti menggunakan staging tervalidasi. "
            "Database aktif saat ini dibackup terlebih dahulu dan rollback "
            "otomatis dijalankan jika health check gagal.\n\n"
            f"Kandidat: {candidate}\n"
            f"Schema: {validation.schema_version}"
            f" (target {validation.target_schema_version})\n"
            f"Period: {validation.period_from or '-'} s.d. "
            f"{validation.period_to or '-'}\n"
            f"Data:\n{counts or '-'}\n"
            + (f"Peringatan:\n{warnings}\n" if warnings else "")
            + "\nKetik GANTI ATTENDANCE OT untuk melanjutkan."
        )
        if not self.services.dialog_service.typed_confirm(
            "Import Database ATTENDANCE & OT",
            message,
            "GANTI ATTENDANCE OT",
        ):
            return
        service = self._attendance_ot_transfer_service()
        if service is None:
            return

        def done(result) -> None:
            self.show_status(self.services.storage_service.resolve_status())
            backup = result.previous_database_backup or "Tidak ada database lama"
            self.services.dialog_service.info(
                "Import Database ATTENDANCE & OT",
                "Database analytics berhasil diaktifkan dan tervalidasi.\n\n"
                f"Active: {result.active_database}\n"
                f"Backup sebelumnya: {backup}\n"
                f"Schema: {result.source_schema_version} -> "
                f"{result.schema_version}\n"
                f"Migrated: {result.migrated}\n"
                f"Analytics rebuilt: {result.rebuilt_analytics}\n\n"
                "Konfigurasi source pada database core tetap dipertahankan. "
                "Path file dengan nama unik akan dikaitkan ulang saat Data Update.",
            )

        self.page.run_task(
            lambda: service.import_candidate(candidate),
            on_success=done,
            message="Mengganti database ATTENDANCE & OT...",
            destructive=True,
            cancellable=False,
        )

    def _attendance_ot_transfer_service(self):
        service = getattr(
            self.services,
            "attendance_ot_database_transfer_service",
            None,
        )
        if service is None:
            self.services.dialog_service.warning(
                "Database ATTENDANCE & OT",
                "Service pengelolaan database analytics tidak tersedia.",
            )
        return service

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
