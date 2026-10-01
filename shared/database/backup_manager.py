"""Validated SQLite backup creation using the SQLite backup API."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.database_validator import DatabaseValidator
from shared.database.exceptions import BackupError
from shared.database.models import BackupResult
from shared.database.time_utils import current_timestamp

logger = logging.getLogger(__name__)


class BackupManager:
    """Create a point-in-time SQLite backup without copying an open file."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
        validator: DatabaseValidator | None = None,
    ) -> None:
        self.connection_factory = (
            connection_factory or SQLiteConnectionFactory()
        )
        self.validator = validator or DatabaseValidator(
            self.connection_factory
        )

    def create_backup(
        self,
        source_database: str | Path,
        destination_backup: str | Path,
        *,
        create_parent: bool = False,
    ) -> BackupResult:
        """Create and validate a backup, leaving the source unchanged."""

        source = Path(source_database)
        destination = Path(destination_backup)
        if source.resolve() == destination.resolve():
            raise BackupError(
                "Backup destination must be different from the source database."
            )
        if destination.exists():
            raise BackupError(
                f"Backup destination already exists: {destination}"
            )
        if create_parent:
            destination.parent.mkdir(parents=True, exist_ok=True)
        elif not destination.parent.exists():
            raise BackupError(
                "Backup parent directory does not exist: "
                f"{destination.parent}"
            )

        source_validation = self.validator.validate(source)
        if not source_validation.is_valid:
            raise BackupError(
                "Source database is not valid: "
                + "; ".join(source_validation.errors)
            )

        created_destination = not destination.exists()
        logger.info("Starting SQLite backup: %s -> %s", source, destination)
        try:
            with self.connection_factory.connect(
                source,
                read_only=True,
            ) as source_connection:
                with self.connection_factory.connect(
                    destination,
                ) as destination_connection:
                    source_connection.backup(destination_connection)
        except (OSError, sqlite3.Error) as exc:
            if created_destination and destination.exists():
                destination.unlink()
            logger.exception("SQLite backup failed: %s", destination)
            raise BackupError(
                f"Unable to create SQLite backup at {destination}: {exc}"
            ) from exc

        validation = self.validator.validate(destination)
        if not validation.is_valid or validation.schema_version is None:
            if created_destination and destination.exists():
                destination.unlink()
            raise BackupError(
                "Backup was created but failed validation: "
                + "; ".join(validation.errors)
            )

        result = BackupResult(
            source_path=source,
            destination_path=destination,
            created_at=current_timestamp(),
            file_size=destination.stat().st_size,
            sha256=self._sha256(destination),
            schema_version=validation.schema_version,
            validation=validation,
        )
        logger.info("SQLite backup completed: %s", destination)
        return result

    @staticmethod
    def suggested_filename(
        timestamp: datetime | None = None,
    ) -> str:
        """Return a safe default backup filename."""

        value = timestamp or datetime.now()
        return f"OAS-K_{value:%Y-%m-%d_%H%M%S}.db"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
