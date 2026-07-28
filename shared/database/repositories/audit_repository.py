"""Repository for configuration audit events."""

from __future__ import annotations

import sqlite3

from shared.database.constants import AUDIT_CHANGE_SOURCES
from shared.database.exceptions import RepositoryError
from shared.database.models import ConfigurationAuditRecord


class AuditRepository:
    """Insert redacted configuration audit records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_audit_record(
        self,
        record: ConfigurationAuditRecord,
    ) -> int:
        """Insert one audit event and return its primary key."""

        if record.change_source not in AUDIT_CHANGE_SOURCES:
            raise ValueError(
                f"Unsupported audit change_source: {record.change_source}"
            )
        try:
            cursor = self.connection.execute(
                """
                INSERT INTO configuration_audit (
                    changed_at,
                    module_code,
                    setting_scope,
                    setting_key,
                    old_value,
                    new_value,
                    change_source,
                    operator,
                    import_batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.changed_at,
                    record.module_code,
                    record.setting_scope,
                    record.setting_key,
                    record.old_value,
                    record.new_value,
                    record.change_source,
                    record.operator,
                    record.import_batch_id,
                ),
            )
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to write configuration audit: {exc}"
            ) from exc
