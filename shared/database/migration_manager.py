"""Sequential, explicit OAS-K database migrations."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import SCHEMA_VERSION
from shared.database.exceptions import MigrationError, SchemaMismatchError
from shared.database.schema_manager import SchemaManager
from shared.database.time_utils import current_timestamp

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MigrationStep:
    """One sequential database migration."""

    from_version: int
    to_version: int
    name: str
    script_name: str


class MigrationManager:
    """Apply registered migrations without resetting user data."""

    def __init__(
        self,
        database_path: str | Path,
        schema_manager: SchemaManager | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.schema_manager = schema_manager or SchemaManager()
        self.connection_factory = SQLiteConnectionFactory()
        self.migrations_path = Path(__file__).parent / "migrations"
        self.steps: tuple[MigrationStep, ...] = (
            MigrationStep(
                1,
                2,
                "Add Outlook payroll period",
                "v1_to_v2.sql",
            ),
        )

    def get_current_version(self) -> int:
        """Return the version stored in the database."""

        return self.schema_manager.get_schema_version(self.database_path)

    @staticmethod
    def get_target_version() -> int:
        """Return the schema version supported by this application."""

        return SCHEMA_VERSION

    def requires_migration(self) -> bool:
        """Return whether an explicit migration is required."""

        current = self.get_current_version()
        target = self.get_target_version()
        if current > target:
            raise SchemaMismatchError(
                f"Database schema version {current} is newer than supported "
                f"version {target}."
            )
        return current < target

    def migrate(self) -> int:
        """Apply every registered migration up to the supported schema."""

        current = self.get_current_version()
        target = self.get_target_version()
        logger.info(
            "Checking database migration: current=%s target=%s",
            current,
            target,
        )
        if current > target:
            raise SchemaMismatchError(
                f"Database schema version {current} is newer than supported "
                f"version {target}."
            )
        if current == target:
            self.schema_manager.ensure_compatible_schema(
                self.database_path,
                target,
            )
            return current
        while current < target:
            step = next(
                (item for item in self.steps if item.from_version == current),
                None,
            )
            if step is None:
                raise MigrationError(
                    f"No migration step is registered from schema {current} "
                    f"to schema {target}."
                )
            self._apply_step(step)
            current = step.to_version

        self.schema_manager.ensure_compatible_schema(
            self.database_path,
            target,
        )
        return current

    def _apply_step(self, step: MigrationStep) -> None:
        script_path = self.migrations_path / step.script_name
        try:
            script = script_path.read_text(encoding="utf-8")
            timestamp = current_timestamp()
            with self.connection_factory.connect(self.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for statement in self.schema_manager._sql_statements(script):
                    connection.execute(statement)
                connection.execute(
                    """
                    UPDATE database_metadata
                    SET schema_version = ?,
                        updated_at = ?,
                        last_migrated_at = ?
                    WHERE metadata_id = 1
                    """,
                    (step.to_version, timestamp, timestamp),
                )
                connection.execute(f"PRAGMA user_version = {step.to_version}")
                connection.commit()
        except (OSError, sqlite3.Error) as exc:
            raise MigrationError(
                f"Migration {step.from_version} to {step.to_version} failed: {exc}"
            ) from exc
        logger.info(
            "Database migration completed: %s -> %s (%s)",
            step.from_version,
            step.to_version,
            step.name,
        )
