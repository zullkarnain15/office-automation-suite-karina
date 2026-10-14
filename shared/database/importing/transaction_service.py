"""Atomic per-module configuration import with audit and batch history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.importing.constants import (
    MODULE_TABLES,
    TABLE_KEYS,
    TABLE_PRIMARY_KEYS,
)
from shared.database.importing.exceptions import ConfigCommitError
from shared.database.importing.models import (
    ChangeOperation,
    ConfigImportCommitRequest,
    ConfigImportCommitResult,
    ConfigImportModuleResult,
    ImportMode,
    MappedModuleConfiguration,
)
from shared.database.importing.preview_builder import database_snapshot_hash
from shared.database.time_utils import current_timestamp

MODE_LABELS = {
    ImportMode.REPLACE_MODULE_CONFIGURATION: "Replace Module Configuration",
    ImportMode.MERGE_REFERENCE_DATA: "Merge Reference/Master Data",
    ImportMode.UPDATE_GLOBAL_SETTINGS: "Replace Module Configuration",
}
SENSITIVE_WORDS = {"password", "secret", "token", "credential"}
OUTLOOK_SENDER_TABLE = "outlook_sender_master"


class ImportTransactionService:
    """Apply one independent transaction per selected module."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def commit(
        self,
        database_path: str | Path,
        request: ConfigImportCommitRequest,
    ) -> ConfigImportCommitResult:
        preview = request.preview
        if not preview.can_commit:
            raise ConfigCommitError("Invalid import preview cannot be committed.")
        if preview.confirmation_required and not request.confirmed:
            raise ConfigCommitError(
                "Import preview requires explicit confirmation."
            )
        with self.connection_factory.connect(
            database_path,
            read_only=True,
        ) as connection:
            current_hash = database_snapshot_hash(connection)
        if current_hash != preview.database_snapshot_hash:
            raise ConfigCommitError(
                "Import preview is stale; rebuild preview before commit."
            )

        mapped_by_module = {
            mapped.module: mapped for mapped in preview.mapped_modules
        }
        results: list[ConfigImportModuleResult] = []
        for module in request.modules:
            mapped = mapped_by_module.get(module)
            if mapped is None:
                results.append(
                    ConfigImportModuleResult(
                        module=module,
                        committed=False,
                        import_batch_id=None,
                        changes_applied=0,
                        error="No mapped configuration for module.",
                    )
                )
                continue
            try:
                result = self._commit_module(
                    Path(database_path),
                    mapped,
                    request,
                )
            except Exception as exc:
                self._record_failed_batch(
                    Path(database_path),
                    mapped,
                    request,
                    str(exc),
                )
                result = ConfigImportModuleResult(
                    module=module,
                    committed=False,
                    import_batch_id=None,
                    changes_applied=0,
                    error=str(exc),
                )
            results.append(result)

        return ConfigImportCommitResult(
            committed=all(result.committed for result in results),
            module_results=tuple(results),
            committed_at=current_timestamp(),
        )

    def _commit_module(
        self,
        database_path: Path,
        mapped: MappedModuleConfiguration,
        request: ConfigImportCommitRequest,
    ) -> ConfigImportModuleResult:
        timestamp = current_timestamp()
        changes = [
            change
            for change in request.preview.changes
            if change.module == mapped.module
            and change.operation
            not in {ChangeOperation.UNCHANGED, ChangeOperation.SKIP}
        ]
        with self.connection_factory.connect(database_path) as connection:
            batch_id = self._insert_batch(
                connection,
                mapped,
                request,
                timestamp,
                "RUNNING",
            )
            for table in MODULE_TABLES[mapped.module]:
                rows = mapped.tables.get(table, ())
                if (
                    mapped.module == "OUTLOOK_REVISI"
                    and table == OUTLOOK_SENDER_TABLE
                    and request.mode == ImportMode.REPLACE_MODULE_CONFIGURATION
                ):
                    self._apply_outlook_sender_changes(
                        connection,
                        rows,
                        changes,
                    )
                    continue
                if request.mode in {
                    ImportMode.REPLACE_MODULE_CONFIGURATION,
                    ImportMode.UPDATE_GLOBAL_SETTINGS,
                }:
                    connection.execute(f"DELETE FROM {table}")
                    self._insert_rows(connection, table, rows)
                else:
                    self._merge_rows(connection, table, rows)

            for change in changes:
                connection.execute(
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
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Excel Import', ?, ?)
                    """,
                    (
                        timestamp,
                        mapped.module,
                        change.setting_scope,
                        change.setting_key,
                        self._redact(change.setting_key, change.old_value),
                        self._redact(change.setting_key, change.new_value),
                        request.operator,
                        batch_id,
                    ),
                )
            connection.execute(
                """
                UPDATE config_import_batches
                SET finished_at = ?, status = 'COMPLETED',
                    rows_read = ?, rows_valid = ?, rows_rejected = 0
                WHERE import_batch_id = ?
                """,
                (timestamp, len(changes), len(changes), batch_id),
            )
        return ConfigImportModuleResult(
            module=mapped.module,
            committed=True,
            import_batch_id=batch_id,
            changes_applied=len(changes),
        )

    @staticmethod
    def _insert_rows(
        connection: sqlite3.Connection,
        table: str,
        rows: tuple[dict[str, Any], ...],
    ) -> None:
        allowed = {
            str(row["name"])
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }
        for row in rows:
            columns = [column for column in row if column in allowed]
            placeholders = ", ".join("?" for _ in columns)
            connection.execute(
                f"""
                INSERT INTO {table} ({", ".join(columns)})
                VALUES ({placeholders})
                """,
                tuple(row[column] for column in columns),
            )

    def _merge_rows(
        self,
        connection: sqlite3.Connection,
        table: str,
        rows: tuple[dict[str, Any], ...],
    ) -> None:
        keys = TABLE_KEYS[table]
        primary_key = TABLE_PRIMARY_KEYS.get(table)
        for row in rows:
            where = " AND ".join(f"{column} = ?" for column in keys)
            connection.execute(
                f"DELETE FROM {table} WHERE {where}",
                tuple(row[column] for column in keys),
            )
            inserted = dict(row)
            if primary_key:
                inserted.pop(primary_key, None)
            self._insert_rows(connection, table, (inserted,))

    def _apply_outlook_sender_changes(
        self,
        connection: sqlite3.Connection,
        rows: tuple[dict[str, Any], ...],
        changes: list[Any],
    ) -> None:
        rows_by_key = {
            _outlook_sender_key(row): row
            for row in rows
        }
        for change in changes:
            if change.setting_scope != OUTLOOK_SENDER_TABLE:
                continue
            key = tuple(json.loads(change.setting_key))
            if change.operation == ChangeOperation.INSERT:
                row = rows_by_key[key]
                inserted = dict(row)
                inserted.pop("sender_id", None)
                self._insert_rows(connection, OUTLOOK_SENDER_TABLE, (inserted,))
            elif change.operation == ChangeOperation.UPDATE:
                row = rows_by_key[key]
                self._update_outlook_sender(connection, row)
            elif change.operation == ChangeOperation.DELETE:
                _delete_outlook_sender(connection, key)

    @staticmethod
    def _update_outlook_sender(
        connection: sqlite3.Connection,
        row: dict[str, Any],
    ) -> None:
        allowed = {
            str(item["name"])
            for item in connection.execute(
                f"PRAGMA table_info({OUTLOOK_SENDER_TABLE})"
            ).fetchall()
        }
        columns = [
            column
            for column in row
            if column in allowed and column not in {"sender_id", "created_at"}
        ]
        assignments = ", ".join(f"{column} = ?" for column in columns)
        connection.execute(
            f"""
            UPDATE {OUTLOOK_SENDER_TABLE}
            SET {assignments}
            WHERE workflow = ?
              AND trim(company_code) = ?
              AND trim(branch_code) = ?
              AND lower(trim(sender_email)) = ?
            """,
            (
                *(row[column] for column in columns),
                *_outlook_sender_key(row),
            ),
        )

    @staticmethod
    def _insert_batch(
        connection: sqlite3.Connection,
        mapped: MappedModuleConfiguration,
        request: ConfigImportCommitRequest,
        timestamp: str,
        status: str,
        error: str | None = None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO config_import_batches (
                module_code,
                source_file_name,
                source_file_hash,
                import_mode,
                started_at,
                finished_at,
                status,
                rows_read,
                rows_valid,
                rows_rejected,
                error_summary,
                operator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?)
            """,
            (
                mapped.module,
                mapped.source_file.name if mapped.source_file else "unified",
                mapped.source_hash or "multiple",
                MODE_LABELS[request.mode],
                timestamp,
                timestamp if status == "FAILED" else None,
                status,
                error,
                request.operator,
            ),
        )
        return int(cursor.lastrowid)

    def _record_failed_batch(
        self,
        database_path: Path,
        mapped: MappedModuleConfiguration,
        request: ConfigImportCommitRequest,
        error: str,
    ) -> None:
        try:
            with self.connection_factory.connect(database_path) as connection:
                self._insert_batch(
                    connection,
                    mapped,
                    request,
                    current_timestamp(),
                    "FAILED",
                    error[:1000],
                )
        except sqlite3.Error:
            return

    @staticmethod
    def _redact(key: str, value: str | None) -> str | None:
        if any(word in key.casefold() for word in SENSITIVE_WORDS):
            return "[REDACTED]"
        if value is None:
            return None
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        for field in list(decoded) if isinstance(decoded, dict) else ():
            if any(word in field.casefold() for word in SENSITIVE_WORDS):
                decoded[field] = "[REDACTED]"
        return json.dumps(decoded, ensure_ascii=False, sort_keys=True)


def _outlook_sender_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("workflow") or "").strip().upper(),
        str(row.get("company_code") or "").strip(),
        str(row.get("branch_code") or "").strip(),
        str(row.get("sender_email") or "").strip().casefold(),
    )


def _delete_outlook_sender(
    connection: sqlite3.Connection,
    key: tuple[str, str, str, str],
) -> None:
    connection.execute(
        f"""
        DELETE FROM {OUTLOOK_SENDER_TABLE}
        WHERE workflow = ?
          AND trim(company_code) = ?
          AND trim(branch_code) = ?
          AND lower(trim(sender_email)) = ?
        """,
        key,
    )
