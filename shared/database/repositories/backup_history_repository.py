"""Repository for backup/import/reset history metadata."""

from __future__ import annotations

import sqlite3

from shared.database.exceptions import RepositoryError
from shared.database.models import BackupHistoryRecord

BACKUP_ACTIONS = {
    "BACKUP",
    "RESTORE_FROM_BACKUP",
    "IMPORT_EXISTING_DATABASE",
    "RESET_TO_DEFAULT",
}


class BackupHistoryRepository:
    """Persist metadata for explicit database lifecycle actions."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_backup_history(self, record: BackupHistoryRecord) -> int:
        """Insert one database action history record."""

        if record.action_type not in BACKUP_ACTIONS:
            raise ValueError(
                f"Unsupported backup action_type: {record.action_type}"
            )
        try:
            cursor = self.connection.execute(
                """
                INSERT INTO backup_history (
                    action_type,
                    source_path,
                    backup_path,
                    database_hash,
                    schema_version,
                    started_at,
                    finished_at,
                    status,
                    validation_result,
                    operator,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.action_type,
                    record.source_path,
                    record.backup_path,
                    record.database_hash,
                    record.schema_version,
                    record.started_at,
                    record.finished_at,
                    record.status,
                    record.validation_result,
                    record.operator,
                    record.notes,
                ),
            )
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to write backup history: {exc}"
            ) from exc

    def get_latest_backup(self) -> BackupHistoryRecord | None:
        """Return the latest explicit successful backup, without mutation."""

        try:
            row = self.connection.execute(
                """
                SELECT backup_id, action_type, source_path, backup_path,
                       database_hash, schema_version, started_at, finished_at,
                       status, validation_result, operator, notes
                FROM backup_history
                WHERE action_type = 'BACKUP'
                ORDER BY COALESCE(finished_at, started_at) DESC, backup_id DESC
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to read latest backup: {exc}") from exc
        return BackupHistoryRecord(**dict(row)) if row is not None else None
