"""Detailed integrity and schema validation for OAS-K databases."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import (
    REQUIRED_INDEXES,
    REQUIRED_TABLES,
    SCHEMA_VERSION,
)
from shared.database.exceptions import DatabaseValidationError
from shared.database.models import DatabaseValidationResult

SQLITE_HEADER = b"SQLite format 3\x00"


class DatabaseValidator:
    """Validate an OAS-K SQLite file without changing it."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
        *,
        expected_version: int = SCHEMA_VERSION,
    ) -> None:
        self.connection_factory = (
            connection_factory or SQLiteConnectionFactory()
        )
        self.expected_version = expected_version

    def validate(
        self,
        database_path: str | Path,
    ) -> DatabaseValidationResult:
        """Return a detailed validation result instead of a bare boolean."""

        path = Path(database_path)
        warnings: list[str] = []
        errors: list[str] = []
        missing_tables: tuple[str, ...] = ()
        missing_indexes: tuple[str, ...] = ()
        schema_version: int | None = None
        integrity_ok = False
        foreign_keys_ok = False

        file_exists = path.is_file()
        if not file_exists:
            errors.append(f"Database file does not exist: {path}")
            return self._result(
                path,
                file_exists=False,
                file_readable=False,
                sqlite_header_ok=False,
                integrity_ok=False,
                foreign_keys_ok=False,
                schema_version=None,
                missing_tables=(),
                missing_indexes=(),
                warnings=warnings,
                errors=errors,
            )

        file_readable = os.access(path, os.R_OK)
        if not file_readable:
            errors.append(f"Database file is not readable: {path}")

        sqlite_header_ok = False
        if file_readable:
            try:
                with path.open("rb") as file_handle:
                    sqlite_header_ok = (
                        file_handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER
                    )
            except OSError as exc:
                errors.append(f"Unable to read SQLite header: {exc}")
            if not sqlite_header_ok:
                errors.append("File does not contain a valid SQLite header.")

        if file_readable and sqlite_header_ok:
            try:
                with self.connection_factory.connect(
                    path,
                    read_only=True,
                ) as connection:
                    integrity_rows = connection.execute(
                        "PRAGMA integrity_check"
                    ).fetchall()
                    integrity_messages = tuple(
                        str(row[0]) for row in integrity_rows
                    )
                    integrity_ok = integrity_messages == ("ok",)
                    if not integrity_ok:
                        errors.append(
                            "SQLite integrity_check failed: "
                            + "; ".join(integrity_messages)
                        )

                    foreign_key_rows = connection.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall()
                    enabled_row = connection.execute(
                        "PRAGMA foreign_keys"
                    ).fetchone()
                    foreign_keys_enabled = (
                        enabled_row is not None and int(enabled_row[0]) == 1
                    )
                    foreign_keys_ok = (
                        foreign_keys_enabled and not foreign_key_rows
                    )
                    if not foreign_keys_enabled:
                        errors.append(
                            "Foreign key enforcement is not enabled."
                        )
                    if foreign_key_rows:
                        errors.append(
                            "SQLite foreign_key_check found violations."
                        )

                    available_tables = self._object_names(
                        connection,
                        "table",
                    )
                    missing_tables = tuple(
                        name
                        for name in self._required_tables()
                        if name not in available_tables
                    )
                    if missing_tables:
                        errors.append(
                            "Missing required tables: "
                            + ", ".join(missing_tables)
                        )

                    available_indexes = self._object_names(
                        connection,
                        "index",
                    )
                    missing_indexes = tuple(
                        name
                        for name in REQUIRED_INDEXES
                        if name not in available_indexes
                    )
                    if missing_indexes:
                        errors.append(
                            "Missing required indexes: "
                            + ", ".join(missing_indexes)
                        )

                    if "database_metadata" in available_tables:
                        metadata_rows = connection.execute(
                            """
                            SELECT schema_version
                            FROM database_metadata
                            WHERE metadata_id = 1
                            """
                        ).fetchall()
                        if len(metadata_rows) != 1:
                            errors.append(
                                "Database metadata singleton is missing "
                                "or duplicated."
                            )
                        else:
                            schema_version = int(
                                metadata_rows[0]["schema_version"]
                            )
                            if schema_version != self.expected_version:
                                errors.append(
                                    "Schema version mismatch: "
                                    f"database={schema_version}, "
                                    f"expected={self.expected_version}."
                                )

                        user_version_row = connection.execute(
                            "PRAGMA user_version"
                        ).fetchone()
                        user_version = (
                            int(user_version_row[0])
                            if user_version_row is not None
                            else 0
                        )
                        if (
                            schema_version is not None
                            and user_version != schema_version
                        ):
                            errors.append(
                                "PRAGMA user_version does not match "
                                "database metadata."
                            )

                    if "global_settings" in available_tables:
                        settings_count_row = connection.execute(
                            "SELECT COUNT(*) FROM global_settings"
                        ).fetchone()
                        settings_count = (
                            int(settings_count_row[0])
                            if settings_count_row is not None
                            else 0
                        )
                        if settings_count == 0:
                            warnings.append(
                                "Global settings are not configured yet."
                            )
                        elif settings_count != 1:
                            errors.append(
                                "Global settings must contain at most "
                                "one singleton row."
                            )
                    if "att_data_repair_settings" in available_tables:
                        count_row = connection.execute(
                            "SELECT COUNT(*) FROM att_data_repair_settings"
                        ).fetchone()
                        count = int(count_row[0]) if count_row is not None else 0
                        if count != 1:
                            errors.append(
                                "Att Data Repair settings must contain exactly "
                                "one singleton row."
                            )
            except (OSError, sqlite3.Error, ValueError) as exc:
                errors.append(f"Unable to validate SQLite database: {exc}")

        return self._result(
            path,
            file_exists=file_exists,
            file_readable=file_readable,
            sqlite_header_ok=sqlite_header_ok,
            integrity_ok=integrity_ok,
            foreign_keys_ok=foreign_keys_ok,
            schema_version=schema_version,
            missing_tables=missing_tables,
            missing_indexes=missing_indexes,
            warnings=warnings,
            errors=errors,
        )

    def validate_or_raise(
        self,
        database_path: str | Path,
    ) -> DatabaseValidationResult:
        """Return a valid result or raise a detailed domain exception."""

        result = self.validate(database_path)
        if not result.is_valid:
            raise DatabaseValidationError(
                "Database validation failed: " + "; ".join(result.errors)
            )
        return result

    @staticmethod
    def _object_names(
        connection: sqlite3.Connection,
        object_type: str,
    ) -> set[str]:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = ? AND name NOT LIKE 'sqlite_%'
            """,
            (object_type,),
        ).fetchall()
        return {str(row[0]) for row in rows}

    def _required_tables(self) -> tuple[str, ...]:
        if self.expected_version < 3:
            return tuple(
                table
                for table in REQUIRED_TABLES
                if table != "att_data_repair_settings"
            )
        return REQUIRED_TABLES

    @staticmethod
    def _result(
        path: Path,
        *,
        file_exists: bool,
        file_readable: bool,
        sqlite_header_ok: bool,
        integrity_ok: bool,
        foreign_keys_ok: bool,
        schema_version: int | None,
        missing_tables: tuple[str, ...],
        missing_indexes: tuple[str, ...],
        warnings: list[str],
        errors: list[str],
    ) -> DatabaseValidationResult:
        return DatabaseValidationResult(
            database_path=path,
            is_valid=not errors,
            file_exists=file_exists,
            file_readable=file_readable,
            sqlite_header_ok=sqlite_header_ok,
            integrity_ok=integrity_ok,
            foreign_keys_ok=foreign_keys_ok,
            schema_version=schema_version,
            missing_tables=missing_tables,
            missing_indexes=missing_indexes,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )
