"""DB4 recovery facade with typed requests and no automatic action."""

from __future__ import annotations

from pathlib import Path

from shared.recovery import (
    ApplicationDataBackupRequest,
    ApplicationDataBackupService,
    CandidateValidator,
    DatabaseBackupRequest,
    DatabaseBackupService,
    ImportDatabaseRequest,
    ImportDatabaseService,
    RecoveryService,
    ResetDatabaseRequest,
    ResetService,
    RestoreRequest,
    RestoreService,
)
from shared.recovery.constants import BackupReason
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry import StorageRegistryService


class RecoveryUIService:
    def __init__(
        self,
        registry: StorageRegistryService,
        *,
        application_version: str,
    ) -> None:
        self.registry = registry
        self.application_version = application_version
        self.candidates = CandidateValidator()

    def validate_candidate(self, path: Path):
        return self.candidates.validate(path)

    def backup_database(self, data_root: Path):
        layout = resolve_storage_layout(data_root)
        return DatabaseBackupService().backup(
            DatabaseBackupRequest(
                layout.database_path,
                layout.backup_root,
                BackupReason.MANUAL,
            )
        )

    def backup_application_data(
        self,
        data_root: Path,
        *,
        include_logs: bool,
        include_diagnostics: bool,
    ):
        layout = resolve_storage_layout(data_root)
        return ApplicationDataBackupService().backup(
            ApplicationDataBackupRequest(
                data_root,
                layout.backup_root,
                self.application_version,
                include_logs=include_logs,
                include_diagnostics=include_diagnostics,
            )
        )

    def restore(
        self,
        source: Path,
        data_root: Path,
        *,
        confirmed: bool,
        write_registry: bool,
    ):
        return RestoreService(self.registry).restore(
            RestoreRequest(
                source,
                data_root,
                confirm=confirmed,
                update_registry=write_registry,
            )
        )

    def import_database(
        self,
        source: Path,
        data_root: Path,
        *,
        confirmed: bool,
        write_registry: bool,
    ):
        return ImportDatabaseService(self.registry).import_database(
            ImportDatabaseRequest(
                source,
                data_root,
                confirm=confirmed,
                update_registry=write_registry,
            )
        )

    def reset(
        self,
        data_root: Path,
        *,
        typed_value: str,
        confirmed: bool,
        write_registry: bool,
    ):
        if typed_value != "RESET":
            raise ValueError("Konfirmasi teks RESET tidak cocok.")
        return ResetService(self.registry).reset(
            ResetDatabaseRequest(
                data_root,
                self.application_version,
                confirm=confirmed,
                update_registry=write_registry,
            )
        )

    @staticmethod
    def recovery_status(*args, **kwargs):
        return RecoveryService().assess(*args, **kwargs)
