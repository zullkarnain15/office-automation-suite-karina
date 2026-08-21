"""Typed configuration audit and backup-history records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigurationAuditRecord:
    """One redacted configuration change audit row."""

    changed_at: str
    module_code: str
    setting_scope: str
    setting_key: str
    change_source: str
    old_value: str | None = None
    new_value: str | None = None
    operator: str | None = None
    import_batch_id: int | None = None
    audit_id: int | None = None


@dataclass(frozen=True, slots=True)
class BackupHistoryRecord:
    """One database backup/restore/import/reset history row."""

    action_type: str
    source_path: str
    started_at: str
    status: str
    backup_path: str | None = None
    database_hash: str | None = None
    schema_version: int | None = None
    finished_at: str | None = None
    validation_result: str | None = None
    operator: str | None = None
    notes: str | None = None
    backup_id: int | None = None
