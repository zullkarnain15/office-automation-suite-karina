"""Redacted recovery audit/history persistence using existing schema tables."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from shared.database import SCHEMA_VERSION, SQLiteConnectionFactory
from shared.database.models import BackupHistoryRecord, ConfigurationAuditRecord
from shared.database.repositories import AuditRepository, BackupHistoryRepository
from shared.database.time_utils import current_timestamp
from shared.recovery.models import RecoveryOperationRecord


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_identifier(path: str | Path | None) -> str:
    return Path(path).name if path else ""


class RecoveryAuditService:
    def __init__(self, factory: SQLiteConnectionFactory | None = None) -> None:
        self.factory = factory or SQLiteConnectionFactory()

    def record_backup(
        self,
        database_path: Path,
        record: BackupHistoryRecord,
    ) -> int:
        with self.factory.connect(database_path) as connection:
            return BackupHistoryRepository(connection).add_backup_history(record)

    def record_operation(
        self,
        database_path: Path,
        record: RecoveryOperationRecord,
        *,
        action_type: str,
        change_source: str,
        backup_path: Path | None = None,
    ) -> tuple[int, int]:
        warning_summary = "; ".join(
            _sanitize_warning(value) for value in record.warnings
        )[:1000] or None
        details = {
            "operation": record.operation,
            "source_type": record.source_type,
            "success": record.success,
            "identifier": record.identifier,
            "old_database_hash": record.old_database_hash,
            "new_database_hash": record.new_database_hash,
            "warnings": warning_summary,
        }
        with self.factory.connect(database_path) as connection:
            history_id = BackupHistoryRepository(connection).add_backup_history(
                BackupHistoryRecord(
                    action_type=action_type,
                    source_path=record.identifier or record.source_type,
                    backup_path=safe_identifier(backup_path) or None,
                    database_hash=record.new_database_hash,
                    schema_version=SCHEMA_VERSION,
                    started_at=record.timestamp,
                    finished_at=current_timestamp(),
                    status="SUCCESS" if record.success else "FAILED",
                    validation_result="VALID" if record.success else "FAILED",
                    operator=_redact(record.operator),
                    notes=warning_summary,
                )
            )
            audit_id = AuditRepository(connection).add_audit_record(
                ConfigurationAuditRecord(
                    changed_at=record.timestamp,
                    module_code="SYSTEM",
                    setting_scope="DATABASE_RECOVERY",
                    setting_key="ACTIVE_DATABASE",
                    old_value=record.old_database_hash,
                    new_value=json.dumps(details, sort_keys=True),
                    change_source=change_source,
                    operator=_redact(record.operator),
                )
            )
            return history_id, audit_id


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if any(token in lowered for token in ("password", "secret", "token", "credential")):
        return "[REDACTED]"
    return value[:255]


def _sanitize_warning(value: str) -> str:
    sanitized = re.sub(
        r"(?i)(?:[a-z]:[\\/]|\\\\|/)[^\s;]+",
        "[PATH]",
        value,
    )
    if any(
        token in sanitized.lower()
        for token in ("password", "secret", "token", "credential")
    ):
        return "[REDACTED WARNING]"
    return sanitized
