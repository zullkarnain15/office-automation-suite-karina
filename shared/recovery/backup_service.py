"""Validated active-database backup workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.database import BackupManager
from shared.database.models import BackupHistoryRecord
from shared.database.time_utils import current_timestamp
from shared.recovery.audit_service import RecoveryAuditService, safe_identifier
from shared.recovery.constants import BACKUP_DATABASE_DIRECTORY, BackupReason
from shared.recovery.models import DatabaseBackupRequest, DatabaseBackupResult


class DatabaseBackupService:
    def __init__(
        self,
        backup_manager: BackupManager | None = None,
        audit_service: RecoveryAuditService | None = None,
    ) -> None:
        self.backup_manager = backup_manager or BackupManager()
        self.audit_service = audit_service or RecoveryAuditService()

    def backup(self, request: DatabaseBackupRequest) -> DatabaseBackupResult:
        source = Path(request.database_path).expanduser()
        root = Path(request.backup_root).expanduser() / BACKUP_DATABASE_DIRECTORY
        started_at = current_timestamp()
        try:
            root.mkdir(parents=True, exist_ok=True)
            destination = self._destination(root, request.overwrite)
            if request.overwrite:
                destination.unlink(missing_ok=True)
            result = self.backup_manager.create_backup(source, destination)
            history_id = self.audit_service.record_backup(
                source,
                BackupHistoryRecord(
                    action_type="BACKUP",
                    source_path=safe_identifier(source),
                    backup_path=safe_identifier(destination),
                    database_hash=result.sha256,
                    schema_version=result.schema_version,
                    started_at=started_at,
                    finished_at=current_timestamp(),
                    status="SUCCESS",
                    validation_result="VALID",
                    operator=request.operator,
                    notes=f"reason={request.reason.value}",
                ),
            )
            return DatabaseBackupResult(
                success=True,
                source_path=source,
                backup_path=destination,
                sha256=result.sha256,
                file_size=result.file_size,
                schema_version=result.schema_version,
                history_id=history_id,
            )
        except Exception as exc:
            return DatabaseBackupResult(
                success=False,
                source_path=source,
                backup_path=None,
                errors=(f"Database backup failed: {exc}",),
            )

    def _destination(self, root: Path, overwrite: bool) -> Path:
        base = root / self.backup_manager.suggested_filename(datetime.now())
        if overwrite or not base.exists():
            return base
        stem = base.stem
        for number in range(1, 10_000):
            candidate = root / f"{stem}_{number:03d}.db"
            if not candidate.exists():
                return candidate
        raise RuntimeError("Unable to allocate a unique backup filename.")


def backup_database(
    database_path: str | Path,
    backup_root: str | Path,
    *,
    reason: BackupReason | str,
    overwrite: bool = False,
    operator: str | None = None,
) -> DatabaseBackupResult:
    return DatabaseBackupService().backup(
        DatabaseBackupRequest(
            database_path=Path(database_path),
            backup_root=Path(backup_root),
            reason=BackupReason(reason),
            overwrite=overwrite,
            operator=operator,
        )
    )
