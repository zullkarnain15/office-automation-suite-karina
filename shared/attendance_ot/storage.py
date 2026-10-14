"""Idempotent, Data-Root-relative storage for Attendance & OT analytics."""

from __future__ import annotations

import sqlite3
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp
from shared.attendance_ot.schema import (
    ANALYTICS_SCHEMA_VERSION,
    AnalyticsSchemaManager,
)

ANALYTICS_RELATIVE_ROOT = Path("analytics") / "attendance_ot"
ANALYTICS_DIRECTORIES = ("database", "cache", "export", "logs")
ANALYTICS_DATABASE_FILENAME = "attendance_ot.db"


@dataclass(frozen=True, slots=True)
class AttendanceOTStorageStatus:
    data_root: Path | None
    analytics_root: Path | None
    database_path: Path | None
    database_exists: bool
    database_valid: bool
    status: str
    size_bytes: int | None = None
    schema_version: int | None = None
    last_initialization_or_migration: str | None = None
    error: str | None = None


class AttendanceOTStorageService:
    """Manage only the dedicated analytics tree; never mutate the core DB."""

    def __init__(self, storage_service) -> None:
        self.storage_service = storage_service
        self.connection_factory = SQLiteConnectionFactory()
        self.schema_manager = AnalyticsSchemaManager(self.connection_factory)

    @staticmethod
    def analytics_root(data_root: Path) -> Path:
        return Path(data_root) / ANALYTICS_RELATIVE_ROOT

    @classmethod
    def database_path(cls, data_root: Path) -> Path:
        return cls.analytics_root(data_root) / "database" / ANALYTICS_DATABASE_FILENAME

    def resolve_status(self) -> AttendanceOTStorageStatus:
        core_status = self.storage_service.resolve_status()
        root = core_status.data_root
        if root is None or not getattr(core_status, "database_valid", False):
            return AttendanceOTStorageStatus(
                root,
                self.analytics_root(root) if root is not None else None,
                self.database_path(root) if root is not None else None,
                False,
                False,
                "Data Root core belum siap",
            )
        analytics_root = self.analytics_root(root)
        database = self.database_path(root)
        if not database.is_file():
            return AttendanceOTStorageStatus(
                root,
                analytics_root,
                database,
                False,
                False,
                "Belum tersedia",
            )
        size = database.stat().st_size
        try:
            metadata = self._read_metadata(database)
            version = int(metadata["schema_version"])
            valid = version == ANALYTICS_SCHEMA_VERSION
            return AttendanceOTStorageStatus(
                root,
                analytics_root,
                database,
                True,
                valid,
                "Siap" if valid else "Perlu migrasi",
                size,
                version,
                str(metadata["last_migrated_at"] or metadata["initialized_at"]),
                None
                if valid
                else (
                    f"Schema analytics v{version}; aplikasi memerlukan "
                    f"v{ANALYTICS_SCHEMA_VERSION}."
                ),
            )
        except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
            journal = Path(str(database) + "-journal")
            recovery_required = journal.is_file() and journal.stat().st_size > 0
            return AttendanceOTStorageStatus(
                root,
                analytics_root,
                database,
                True,
                False,
                "Recovery required" if recovery_required else "Tidak valid",
                size,
                error=(
                    "Interrupted transaction terdeteksi; gunakan Repair ATTENDANCE & OT. "
                    + str(exc)
                    if recovery_required
                    else str(exc)
                ),
            )

    def repair_interrupted_transaction(self) -> dict[str, object]:
        core_status = self.storage_service.resolve_status()
        if core_status.data_root is None or not getattr(
            core_status, "database_valid", False
        ):
            raise RuntimeError("Data Root aktif belum siap.")
        database = self.database_path(Path(core_status.data_root)).resolve()
        journal = Path(str(database) + "-journal")
        if not database.is_file():
            raise RuntimeError("attendance_ot.db tidak ditemukan.")
        if not journal.is_file() or journal.stat().st_size == 0:
            raise RuntimeError("Rollback journal aktif tidak ditemukan.")

        recovery_root = database.parent / "recovery"
        recovery_root.mkdir(parents=True, exist_ok=True)
        operation = recovery_root / f"interrupted-{uuid.uuid4().hex}"
        operation.mkdir()
        database_copy = operation / database.name
        journal_copy = operation / journal.name
        shutil.copy2(database, database_copy)
        shutil.copy2(journal, journal_copy)

        try:
            with self.connection_factory.connect(database) as connection:
                quick = connection.execute("PRAGMA quick_check").fetchone()
                if quick is None or quick[0] != "ok":
                    raise sqlite3.DatabaseError(
                        f"SQLite quick_check gagal: {quick[0] if quick else '-'}"
                    )
                foreign_keys = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if foreign_keys:
                    raise sqlite3.DatabaseError(
                        f"Foreign-key check gagal ({len(foreign_keys)} temuan)."
                    )
                metadata = connection.execute(
                    "SELECT schema_version FROM analytics_metadata WHERE metadata_id=1"
                ).fetchone()
                user_version = connection.execute("PRAGMA user_version").fetchone()
                if (
                    metadata is None
                    or user_version is None
                    or int(metadata[0]) != int(user_version[0])
                ):
                    raise sqlite3.DatabaseError(
                        "Schema metadata dan PRAGMA user_version tidak sesuai."
                    )
        except Exception as exc:
            raise RuntimeError(
                f"Recovery gagal; salinan awal dipertahankan di {operation}: {exc}"
            ) from exc

        from shared.attendance_ot.backup import verified_backup

        verified = verified_backup(database, "after-interrupted-recovery")
        status = self.resolve_status()
        if not status.database_valid:
            raise RuntimeError(status.error or "Database gagal divalidasi setelah recovery.")
        return {
            "database": str(database),
            "pre_recovery_copy": str(operation),
            "verified_backup": str(verified),
            "schema_version": status.schema_version,
        }

    def initialize(self) -> AttendanceOTStorageStatus:
        core_status = self.storage_service.resolve_status()
        if core_status.data_root is None or not getattr(
            core_status, "database_valid", False
        ):
            raise RuntimeError(
                "Data Root aktif belum siap. Initialize Data Location terlebih dahulu."
            )
        root = Path(core_status.data_root)
        analytics_root = self.analytics_root(root)
        database = self.database_path(root)

        if database.exists():
            try:
                metadata = self._read_metadata(database)
                current_version = int(metadata["schema_version"])
            except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    "attendance_ot.db sudah ada tetapi bukan database analytics "
                    f"yang kompatibel; file tidak diubah. Detail: {exc}"
                ) from exc
            self.schema_manager.migrate_to_current(database, current_version)
            status = self.resolve_status()
            if not status.database_valid:
                raise RuntimeError(
                    status.error or "Database analytics tidak kompatibel."
                )
            return status

        for name in ANALYTICS_DIRECTORIES:
            (analytics_root / name).mkdir(parents=True, exist_ok=True)

        timestamp = current_timestamp()
        with self.connection_factory.connect(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE analytics_metadata (
                    metadata_id INTEGER PRIMARY KEY CHECK (metadata_id = 1),
                    database_uuid TEXT NOT NULL UNIQUE,
                    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                    initialized_at TEXT NOT NULL,
                    last_migrated_at TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO analytics_metadata (
                    metadata_id, database_uuid, schema_version,
                    initialized_at, last_migrated_at
                ) VALUES (1, ?, ?, ?, NULL)
                """,
                (str(uuid.uuid4()), 1, timestamp),
            )
            connection.execute("PRAGMA user_version = 1")
            connection.commit()

        self.schema_manager.migrate_to_current(database, 1)

        status = self.resolve_status()
        if not status.database_valid:
            raise RuntimeError(status.error or "Database analytics gagal divalidasi.")
        return status

    def _read_metadata(self, database: Path) -> sqlite3.Row:
        with self.connection_factory.connect(database, read_only=True) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='analytics_metadata'"
            ).fetchone()
            if table is None:
                raise sqlite3.DatabaseError("Tabel analytics_metadata tidak ditemukan.")
            row = connection.execute(
                """
                SELECT schema_version, initialized_at, last_migrated_at
                FROM analytics_metadata WHERE metadata_id = 1
                """
            ).fetchone()
            if row is None:
                raise sqlite3.DatabaseError("Metadata analytics tidak ditemukan.")
            user_version = connection.execute("PRAGMA user_version").fetchone()
            if user_version is None or int(user_version[0]) != int(
                row["schema_version"]
            ):
                raise sqlite3.DatabaseError(
                    "Schema metadata dan PRAGMA user_version tidak sesuai."
                )
            return row
