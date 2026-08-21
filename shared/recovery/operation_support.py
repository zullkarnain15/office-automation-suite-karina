"""Shared safeguards for destructive recovery operations."""

from __future__ import annotations

from pathlib import Path

from shared.recovery.audit_service import RecoveryAuditService, sha256_file
from shared.recovery.backup_service import DatabaseBackupService
from shared.recovery.constants import BackupReason
from shared.recovery.models import (
    DatabaseBackupRequest,
    RecoveryOperationRecord,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.storage_validator import validate_data_root


def validate_active_storage(data_root: Path) -> None:
    result = validate_data_root(data_root)
    errors: list[str] = []
    if not result.exists:
        errors.append("Active Data Root does not exist.")
    if not result.drive_available:
        errors.append("Active Data Root drive is unavailable.")
    if not result.is_local:
        errors.append("Active Data Root must be local.")
    if not result.writable:
        errors.append("Active Data Root is not writable.")
    if errors:
        raise RuntimeError(" ".join(errors))


def create_pre_operation_backup(
    data_root: Path,
    *,
    reason: BackupReason,
    operator: str | None,
    force_without_prebackup: bool,
    service: DatabaseBackupService,
) -> tuple[Path | None, tuple[str, ...]]:
    layout = resolve_storage_layout(data_root)
    if not layout.database_path.exists():
        return None, ()
    result = service.backup(
        DatabaseBackupRequest(
            database_path=layout.database_path,
            backup_root=layout.backup_root,
            reason=reason,
            operator=operator,
        )
    )
    if result.success:
        return result.backup_path, result.warnings
    if not force_without_prebackup:
        raise RuntimeError(
            "Current database backup failed; activation cancelled: "
            + "; ".join(result.errors)
        )
    return None, (
        "Explicit force flag accepted: current database backup failed.",
        *result.errors,
    )


def record_recovery_operation(
    database_path: Path,
    *,
    operation: str,
    source_type: str,
    action_type: str,
    change_source: str,
    success: bool,
    timestamp: str,
    operator: str | None,
    identifier: str,
    old_hash: str | None,
    new_hash: str | None,
    warnings: tuple[str, ...],
    backup_path: Path | None,
    audit_service: RecoveryAuditService,
) -> None:
    audit_service.record_operation(
        database_path,
        RecoveryOperationRecord(
            operation=operation,
            source_type=source_type,
            success=success,
            timestamp=timestamp,
            operator=operator,
            identifier=identifier,
            old_database_hash=old_hash,
            new_database_hash=new_hash,
            warnings=warnings,
        ),
        action_type=action_type,
        change_source=change_source,
        backup_path=backup_path,
    )


def hash_if_readable(path: Path) -> str | None:
    try:
        return sha256_file(path) if path.is_file() else None
    except OSError:
        return None
