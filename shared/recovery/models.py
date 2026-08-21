"""Typed requests and results for DB4 recovery workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shared.recovery.constants import BackupReason, RecoveryAction, RecoveryStatus


@dataclass(frozen=True, slots=True)
class CandidateValidationResult:
    candidate_path: Path
    exists: bool
    readable: bool
    sqlite_valid: bool
    integrity_ok: bool
    foreign_keys_ok: bool
    schema_version: int | None
    schema_compatible: bool
    required_tables_ok: bool
    metadata_ok: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def can_activate(self) -> bool:
        return (
            self.exists
            and self.readable
            and self.sqlite_valid
            and self.integrity_ok
            and self.foreign_keys_ok
            and self.schema_compatible
            and self.required_tables_ok
            and self.metadata_ok
            and not self.errors
        )


@dataclass(frozen=True, slots=True)
class DatabaseBackupRequest:
    database_path: Path
    backup_root: Path
    reason: BackupReason = BackupReason.MANUAL
    overwrite: bool = False
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class DatabaseBackupResult:
    success: bool
    source_path: Path
    backup_path: Path | None
    sha256: str | None = None
    file_size: int = 0
    schema_version: int | None = None
    history_id: int | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplicationDataBackupRequest:
    data_root: Path
    backup_root: Path
    application_version: str
    include_logs: bool = False
    include_diagnostics: bool = False
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class BackupManifest:
    format_version: int
    application_version: str
    schema_version: int
    created_at: str
    source_data_root: str
    database_relative_path: str
    database_sha256: str
    included_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    recorder_profile_count: int


@dataclass(frozen=True, slots=True)
class ApplicationDataBackupResult:
    success: bool
    source_data_root: Path
    backup_path: Path | None
    manifest: BackupManifest | None = None
    sha256: str | None = None
    history_id: int | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RestoreRequest:
    source_backup: Path
    active_data_root: Path
    confirm: bool
    restore_recorder_profiles: bool = True
    force_without_prebackup: bool = False
    update_registry: bool = False
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class RestoreResult:
    success: bool
    source_backup: Path
    active_database: Path
    pre_operation_backup: Path | None = None
    recorder_profiles_restored: int = 0
    registry_updated: bool = False
    rolled_back: bool = False
    operation_id: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportDatabaseRequest:
    source_database: Path
    active_data_root: Path
    confirm: bool
    force_without_prebackup: bool = False
    update_registry: bool = False
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class ImportDatabaseResult:
    success: bool
    source_database: Path
    active_database: Path
    pre_operation_backup: Path | None = None
    registry_updated: bool = False
    rolled_back: bool = False
    operation_id: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResetDatabaseRequest:
    active_data_root: Path
    application_version: str
    confirm: bool
    preserve_recorder_profiles: bool = True
    force_without_prebackup: bool = False
    update_registry: bool = False
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class ResetDatabaseResult:
    success: bool
    active_database: Path
    pre_operation_backup: Path | None = None
    registry_updated: bool = False
    recorder_profiles_preserved: bool = True
    rolled_back: bool = False
    operation_id: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecoveryRecommendation:
    action: RecoveryAction
    reason: str
    priority: int


@dataclass(frozen=True, slots=True)
class RecoveryState:
    primary_status: RecoveryStatus
    statuses: tuple[RecoveryStatus, ...]
    recommendations: tuple[RecoveryRecommendation, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecoveryOperationRecord:
    operation: str
    source_type: str
    success: bool
    timestamp: str
    operator: str | None = None
    identifier: str | None = None
    old_database_hash: str | None = None
    new_database_hash: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
