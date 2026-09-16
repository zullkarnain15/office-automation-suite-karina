"""Backup-first database migration used during application startup."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from shared.database.backup_manager import BackupManager
from shared.database.constants import SCHEMA_VERSION
from shared.database.database_validator import DatabaseValidator
from shared.database.exceptions import StartupDatabaseMigrationError
from shared.database.migration_manager import MigrationManager

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class StartupMigrationResult:
    status: str
    database_path: Path | None
    previous_version: int | None
    current_version: int | None
    backup_path: Path | None = None


class StartupDatabaseMigrator:
    """Bring an existing OAS-K database to the supported schema safely."""

    def ensure_current(
        self,
        database_path: str | Path | None,
        backup_root: str | Path | None,
        *,
        progress: ProgressCallback | None = None,
    ) -> StartupMigrationResult:
        database = Path(database_path) if database_path is not None else None
        if database is None or not database.is_file():
            return StartupMigrationResult(
                "NO_DATABASE",
                database,
                None,
                None,
            )

        notify = progress or (lambda _message: None)
        notify("Memeriksa versi database...")
        try:
            migration = MigrationManager(database)
            current = migration.get_current_version()
            target = SCHEMA_VERSION

            if current == target:
                DatabaseValidator().validate_or_raise(database)
                return StartupMigrationResult(
                    "CURRENT",
                    database,
                    current,
                    current,
                )
            if current > target:
                raise StartupDatabaseMigrationError(
                    f"Schema database versi {current} lebih baru daripada "
                    f"versi {target} yang didukung aplikasi."
                )
            if backup_root is None:
                raise StartupDatabaseMigrationError(
                    "Folder backup database tidak dapat ditentukan."
                )

            legacy_validator = DatabaseValidator(expected_version=current)
            legacy_validation = legacy_validator.validate(database)
            if not legacy_validation.is_valid:
                raise StartupDatabaseMigrationError(
                    "Database lama gagal validasi sebelum migrasi: "
                    + "; ".join(legacy_validation.errors)
                )

            notify("Mencadangkan database sebelum pembaruan...")
            backup_path = self._available_backup_path(
                Path(backup_root),
                target,
            )
            BackupManager(validator=legacy_validator).create_backup(
                database,
                backup_path,
                create_parent=True,
            )

            notify(f"Memperbarui schema database v{current} ke v{target}...")
            try:
                migrated_version = migration.migrate()
            except Exception as exc:
                raise StartupDatabaseMigrationError(
                    "Migrasi database gagal. Database backup tersedia di "
                    f"{backup_path}. Detail: {exc}"
                ) from exc

            notify("Memvalidasi database setelah pembaruan...")
            validation = DatabaseValidator().validate(database)
            if not validation.is_valid:
                raise StartupDatabaseMigrationError(
                    "Database hasil migrasi gagal validasi. Hentikan penggunaan "
                    f"dan gunakan backup {backup_path}. Detail: "
                    + "; ".join(validation.errors)
                )

            logger.info(
                "Startup database migration completed: %s -> %s; backup=%s",
                current,
                migrated_version,
                backup_path,
            )
            return StartupMigrationResult(
                "MIGRATED",
                database,
                current,
                migrated_version,
                backup_path,
            )
        except StartupDatabaseMigrationError:
            raise
        except Exception as exc:
            raise StartupDatabaseMigrationError(
                f"Pemeriksaan database startup gagal: {exc}"
            ) from exc

    @staticmethod
    def _available_backup_path(backup_root: Path, target_version: int) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = backup_root / (
            f"OAS-K_before_schema_v{target_version}_{timestamp}.db"
        )
        if not base.exists():
            return base
        counter = 1
        while True:
            candidate = base.with_name(
                f"{base.stem}_{counter:03d}{base.suffix}"
            )
            if not candidate.exists():
                return candidate
            counter += 1
