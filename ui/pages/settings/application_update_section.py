"""Manual application update package section for Settings."""

from __future__ import annotations

import webbrowser
import os
from pathlib import Path
from tkinter import ttk

from shared.update import ApplicationUpdateService
from ui.pages.settings.common import SettingsSection
from ui.widgets import ResultSummary

GITHUB_RELEASES_URL = (
    "https://github.com/zullkarnain15/office-automation-suite-karina/releases"
)


class ApplicationUpdateSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self._selected_package: Path | None = None
        self._last_validation = None
        self._prepared_transaction = None
        self.update_service = ApplicationUpdateService()

        ttk.Label(self, text="Application Update", style="SectionHeader.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            self,
            text=(
                "Manual application-only update. Aplikasi aktif belum diganti "
                "sampai update diterapkan secara manual."
            ),
            style="SectionHeader.TLabel",
            wraplength=820,
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        details = ttk.Frame(self, style="OASK.TFrame")
        details.grid(row=2, column=0, sticky="ew")
        details.columnconfigure(1, weight=1)
        rows = (
            ("Current Version", self.page.context.application_version),
            ("Update Source", "GitHub Release - Manual Download"),
        )
        for index, (label, value) in enumerate(rows):
            ttk.Label(details, text=label, style="SectionHeader.TLabel").grid(
                row=index, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(details, text=value, style="CardBody.TLabel").grid(
                row=index, column=1, sticky="w", pady=3
            )
        ttk.Label(details, text="Selected Package", style="SectionHeader.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=3
        )
        self.selected_var = ttk.Label(details, text="-", style="CardBody.TLabel")
        self.selected_var.grid(row=2, column=1, sticky="w", pady=3)

        buttons = ttk.Frame(self, style="OASK.TFrame")
        buttons.grid(row=3, column=0, sticky="w", pady=8)
        actions = (
            ("Open GitHub Releases", self.open_releases),
            ("Select Update Package", self.select_package),
            ("Validate Package", self.validate_package),
            ("Open Staging Folder", self.open_staging_folder),
            ("Cancel Prepared Update", self.cancel_prepared_update),
        )
        for index, (text, command) in enumerate(actions):
            button = ttk.Button(buttons, text=text, command=command)
            button.grid(row=0, column=index, padx=4, pady=4)
            self.page.register_action(button)
        self.prepare_button = ttk.Button(
            buttons,
            text="Prepare Update",
            command=self.prepare_update,
        )
        self.prepare_button.grid(row=1, column=0, padx=4, pady=4, sticky="w")
        self.page.register_action(self.prepare_button)
        self.apply_button = ttk.Button(
            buttons,
            text="Close and Apply Update",
            command=self.apply_update,
        )
        self.apply_button.grid(row=1, column=1, padx=4, pady=4, sticky="w")
        self.page.register_action(self.apply_button)

        self.result = ResultSummary(self)
        self.result.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        self.refresh_action_state()

    def on_selected(self) -> None:
        self.refresh_prepared_update()

    def open_releases(self) -> None:
        webbrowser.open(GITHUB_RELEASES_URL)

    def select_package(self) -> None:
        package = self.services.dialog_service.select_file(
            title="Pilih OAS-K Update Package",
            filetypes=(("OAS-K Update ZIP", "OAS-K_Update_v*.zip"), ("ZIP", "*.zip")),
        )
        if package is None:
            return
        self._selected_package = package
        self._last_validation = None
        self._prepared_transaction = None
        self.selected_var.configure(text=str(package))
        self.result.show_lines(["Package dipilih. Klik Validate Package."])
        self.refresh_action_state()

    def validate_package(self) -> None:
        if self._selected_package is None:
            self.services.dialog_service.warning(
                "Validate Package",
                "Pilih file ZIP update terlebih dahulu.",
            )
            return
        status = self.active_status()
        if not status.database_valid or status.schema_version is None:
            self.services.dialog_service.warning(
                "Validate Package",
                "Database aktif harus valid agar schema package bisa dibandingkan.",
            )
            return
        schema_version = status.schema_version
        self.page.run_task(
            lambda: self.update_service.validate_package(
                self._selected_package,
                current_version=self.page.context.application_version,
                active_schema_version=schema_version,
            ),
            on_success=self._show_validation,
            message="Memvalidasi update package...",
        )

    def prepare_update(self) -> None:
        if self._selected_package is None or not self._is_validated():
            self.services.dialog_service.warning(
                "Prepare Update",
                "Package harus lolos validasi sebelum Prepare Update.",
            )
            return
        data_root = self.active_data_root()
        if not self.services.dialog_service.confirm(
            "Prepare Update",
            (
                "Database aktif akan dibackup via recovery service, package akan "
                "diekstrak ke staging Data Root, dan EXE aktif belum diganti."
            ),
        ):
            return
        self.page.run_task(
            lambda: self.update_service.prepare_update(
                self._selected_package,
                current_version=self.page.context.application_version,
                data_root=data_root,
            ),
            on_success=self._show_prepared,
            message="Menyiapkan update application-only...",
            destructive=True,
            cancellable=False,
        )

    def _show_validation(self, result) -> None:
        self._last_validation = result
        if not result.valid or result.info is None:
            self.result.show_lines(
                ["Validation: FAILED", *result.errors, *result.warnings]
            )
            self.refresh_action_state()
            return
        manifest = result.info.manifest
        self.result.show_lines(
            [
                "Validation: PASSED",
                f"Target Version: {manifest.version}",
                f"Package Type: {manifest.package_type}",
                f"Database Schema: {manifest.database_schema_from}",
                f"Files: {result.info.file_count}",
                f"Package SHA-256: {result.info.package_sha256}",
                "Prepare Update belum mengganti aplikasi aktif.",
                *result.warnings,
            ]
        )
        self.refresh_action_state()

    def _show_prepared(self, result) -> None:
        if result.transaction_path is not None:
            self._prepared_transaction = self.update_service.load_pending_transaction(
                self.active_data_root()
            )
        self.result.show_lines(
            [
                "Update Ready",
                f"Status: {result.status}",
                f"Current Version: {result.current_version}",
                f"Target Version: {result.target_version}",
                "Database Change: None",
                "Backup Status: Completed",
                "Staging Status: Completed",
                f"Backup: {result.backup_path}",
                f"Staging: {result.staging_path}",
                f"Pending: {result.pending_path}",
                "Aplikasi aktif belum diganti. Database migration belum dijalankan.",
            ]
        )
        self.refresh_action_state()

    def refresh_action_state(self) -> None:
        busy = self.page.is_busy
        state = "normal" if self._is_validated() and not busy else "disabled"
        self.prepare_button.configure(state=state)
        apply_state = (
            "normal"
            if self._prepared_transaction is not None
            and self._prepared_transaction.status == "STAGED"
            and not busy
            else "disabled"
        )
        self.apply_button.configure(state=apply_state)

    def _is_validated(self) -> bool:
        return bool(self._last_validation and self._last_validation.valid)

    def refresh_prepared_update(self) -> None:
        try:
            transaction = self.update_service.load_pending_transaction(
                self.active_data_root()
            )
        except Exception:
            transaction = None
        self._prepared_transaction = transaction if transaction and transaction.status == "STAGED" else None
        if self._prepared_transaction is not None:
            self.result.show_lines(
                [
                    "Update Ready",
                    f"Current Version: {self._prepared_transaction.current_version}",
                    f"Target Version: {self._prepared_transaction.target_version}",
                    "Database Change: None",
                    "Backup Status: Completed",
                    "Staging Status: Completed",
                    f"Rollback Folder: {self._prepared_transaction.rollback_path}",
                    f"Log Path: {self._prepared_transaction.log_path}",
                ]
            )
        self.refresh_action_state()

    def open_staging_folder(self) -> None:
        if self._prepared_transaction is None:
            self.refresh_prepared_update()
        if self._prepared_transaction is None:
            self.services.dialog_service.warning("Open Staging Folder", "Tidak ada update STAGED.")
            return
        if not self.services.file_system_service.open_folder(
            self._prepared_transaction.staging_path
        ):
            self.services.dialog_service.warning(
                "Open Staging Folder",
                str(self._prepared_transaction.staging_path),
            )

    def cancel_prepared_update(self) -> None:
        if not self.services.dialog_service.confirm(
            "Cancel Prepared Update",
            "Staging update akan dihapus. Backup database tetap dipertahankan.",
        ):
            return
        data_root = self.active_data_root()
        self.page.run_task(
            lambda: self.update_service.cancel_staged_update(data_root),
            on_success=lambda transaction: (
                setattr(self, "_prepared_transaction", None),
                self.result.show_lines(
                    [
                        f"Status: {transaction.status}",
                        "Prepared update dibatalkan. Database dan Application Root tidak berubah.",
                    ]
                ),
                self.refresh_action_state(),
            ),
            message="Membatalkan prepared update...",
            destructive=True,
            cancellable=False,
        )

    def apply_update(self) -> None:
        if self._prepared_transaction is None:
            self.refresh_prepared_update()
        if self._prepared_transaction is None:
            self.services.dialog_service.warning("Close and Apply Update", "Tidak ada update STAGED.")
            return
        message = (
            f"Current Version: {self._prepared_transaction.current_version}\n"
            f"Target Version: {self._prepared_transaction.target_version}\n"
            f"Application Root: {self._prepared_transaction.application_root}\n"
            f"Rollback Folder: {self._prepared_transaction.rollback_path}\n"
            f"Database Backup: {self._prepared_transaction.database_backup_path}\n"
            "Expected Downtime: 1-2 menit\n"
            "Data Impact: None\n\n"
            "OAS-K akan ditutup dan dibuka kembali. Lanjutkan?"
        )
        if not self.services.dialog_service.confirm("Close and Apply Update", message):
            return
        data_root = self.active_data_root()

        def done(result) -> None:
            self.result.show_lines(
                [
                    "Updater eksternal sudah dijalankan.",
                    f"Updater PID: {result.process_id}",
                    f"Transaction: {result.transaction.transaction_path}",
                    "OAS-K akan ditutup secara graceful.",
                ]
            )
            close = self.page.context.request_close
            if close is not None:
                self.page.after(250, close)
            else:
                self.page.after(250, self.page.winfo_toplevel().destroy)

        self.page.run_task(
            lambda: self.update_service.request_apply_update(
                data_root,
                wait_pid=os.getpid(),
            ),
            on_success=done,
            message="Menjalankan updater eksternal...",
            destructive=True,
            cancellable=False,
        )
