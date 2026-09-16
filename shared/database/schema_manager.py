"""Initialization and compatibility checks for the OAS-K schema."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterator
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import REQUIRED_TABLES, SCHEMA_VERSION
from shared.database.exceptions import (
    DatabaseInitializationError,
    SchemaMismatchError,
)
from shared.database.models import DatabaseMetadata
from shared.database.time_utils import current_timestamp

logger = logging.getLogger(__name__)


class SchemaManager:
    """Create the current schema once and reject incompatible databases safely."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.connection_factory = (
            connection_factory or SQLiteConnectionFactory()
        )
        self.schema_file = Path(__file__).parent / "schema" / "v1.sql"
        self.migrations_path = Path(__file__).parent / "migrations"

    def initialize_database(
        self,
        database_path: str | Path,
        application_version: str,
        *,
        create_parent: bool = False,
    ) -> DatabaseMetadata:
        """Create the current schema atomically, or validate an existing database."""

        path = Path(database_path)
        if not application_version.strip():
            raise ValueError("application_version must not be empty.")

        if self.is_initialized(path):
            self.ensure_compatible_schema(path, SCHEMA_VERSION)
            metadata = self._read_metadata(path)
            logger.info("Database already initialized: %s", path)
            return metadata

        try:
            with self.connection_factory.connect(
                path,
                create_parent=create_parent,
            ) as connection:
                existing_tables = self._user_tables(connection)
                if existing_tables:
                    raise DatabaseInitializationError(
                        "Database contains tables but has no valid OAS-K "
                        f"metadata: {', '.join(existing_tables)}"
                    )

                schema_sql = self.schema_file.read_text(encoding="utf-8")
                timestamp = current_timestamp()
                connection.execute("BEGIN IMMEDIATE")
                for statement in self._sql_statements(schema_sql):
                    connection.execute(statement)
                for version in range(1, SCHEMA_VERSION):
                    migration_file = self.migrations_path / (
                        f"v{version}_to_v{version + 1}.sql"
                    )
                    migration_sql = migration_file.read_text(encoding="utf-8")
                    for statement in self._sql_statements(migration_sql):
                        connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO database_metadata (
                        metadata_id,
                        database_uuid,
                        schema_version,
                        application_version,
                        created_at,
                        updated_at,
                        last_migrated_at
                    ) VALUES (1, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        str(uuid.uuid4()),
                        SCHEMA_VERSION,
                        application_version.strip(),
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                connection.commit()
        except DatabaseInitializationError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseInitializationError(
                f"Unable to initialize OAS-K database at {path}: {exc}"
            ) from exc

        self.ensure_compatible_schema(path, SCHEMA_VERSION)
        logger.info("Initialized OAS-K schema v%s: %s", SCHEMA_VERSION, path)
        return self._read_metadata(path)

    def is_initialized(self, database_path: str | Path) -> bool:
        """Return whether the path contains one valid metadata singleton."""

        path = Path(database_path)
        if not path.is_file():
            return False
        try:
            with self.connection_factory.connect(
                path,
                read_only=True,
            ) as connection:
                table = connection.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'database_metadata'
                    """
                ).fetchone()
                if table is None:
                    return False
                row = connection.execute(
                    "SELECT COUNT(*) FROM database_metadata"
                ).fetchone()
                return row is not None and int(row[0]) == 1
        except (OSError, sqlite3.Error):
            return False

    def get_schema_version(self, database_path: str | Path) -> int:
        """Read the schema version stored inside database metadata."""

        metadata = self._read_metadata(Path(database_path))
        return metadata.schema_version

    def verify_required_tables(
        self,
        database_path: str | Path,
    ) -> tuple[str, ...]:
        """Return required schema tables missing from the database."""

        path = Path(database_path)
        try:
            with self.connection_factory.connect(
                path,
                read_only=True,
            ) as connection:
                available = set(self._user_tables(connection))
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseInitializationError(
                f"Unable to inspect database tables at {path}: {exc}"
            ) from exc

        return tuple(
            table for table in REQUIRED_TABLES if table not in available
        )

    def ensure_compatible_schema(
        self,
        database_path: str | Path,
        expected_version: int = SCHEMA_VERSION,
    ) -> None:
        """Raise on metadata, user-version, or required-table mismatch."""

        path = Path(database_path)
        actual_version = self.get_schema_version(path)
        if actual_version != expected_version:
            direction = (
                "newer than this application"
                if actual_version > expected_version
                else "older and requires an explicit migration"
            )
            raise SchemaMismatchError(
                f"Database schema version {actual_version} is {direction}; "
                f"expected version {expected_version}."
            )

        missing_tables = self.verify_required_tables(path)
        if missing_tables:
            raise SchemaMismatchError(
                "Database is missing required tables: "
                + ", ".join(missing_tables)
            )

        try:
            with self.connection_factory.connect(
                path,
                read_only=True,
            ) as connection:
                user_version_row = connection.execute(
                    "PRAGMA user_version"
                ).fetchone()
                user_version = (
                    int(user_version_row[0])
                    if user_version_row is not None
                    else 0
                )
        except sqlite3.Error as exc:
            raise SchemaMismatchError(
                f"Unable to inspect PRAGMA user_version for {path}: {exc}"
            ) from exc

        if user_version != expected_version:
            raise SchemaMismatchError(
                "Schema metadata and PRAGMA user_version disagree: "
                f"metadata={actual_version}, user_version={user_version}."
            )

    def _read_metadata(self, path: Path) -> DatabaseMetadata:
        try:
            with self.connection_factory.connect(
                path,
                read_only=True,
            ) as connection:
                row = connection.execute(
                    """
                    SELECT
                        metadata_id,
                        database_uuid,
                        schema_version,
                        application_version,
                        created_at,
                        updated_at,
                        last_migrated_at
                    FROM database_metadata
                    WHERE metadata_id = 1
                    """
                ).fetchone()
        except (OSError, sqlite3.Error) as exc:
            raise DatabaseInitializationError(
                f"Unable to read database metadata at {path}: {exc}"
            ) from exc

        if row is None:
            raise DatabaseInitializationError(
                f"Database metadata is missing at {path}."
            )
        return DatabaseMetadata(**dict(row))

    @staticmethod
    def _user_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    @staticmethod
    def _sql_statements(script: str) -> Iterator[str]:
        buffer = ""
        for line in script.splitlines(keepends=True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                statement = buffer.strip()
                buffer = ""
                if statement:
                    yield statement
        if buffer.strip():
            raise DatabaseInitializationError(
                "Schema SQL ends with an incomplete statement."
            )
