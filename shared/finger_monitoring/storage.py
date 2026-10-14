"""Data-Root-relative, opt-in storage for Finger Monitoring."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shared.finger_monitoring.schema import FingerMonitoringSchemaManager

FINGER_MONITORING_RELATIVE_ROOT = Path("monitoring") / "finger"
FINGER_MONITORING_DATABASE_FILENAME = "finger_monitoring.db"
FINGER_MONITORING_DIRECTORIES = ("database", "backup", "export", "logs")


@dataclass(frozen=True, slots=True)
class FingerMonitoringStorageStatus:
    data_root: Path | None
    monitoring_root: Path | None
    database_path: Path | None
    database_exists: bool
    database_valid: bool
    status: str
    schema_version: int | None = None
    size_bytes: int | None = None
    error: str | None = None


class FingerMonitoringStorageService:
    """Manage only Finger Monitoring files, never the OAS-K core database."""

    def __init__(self, storage_service) -> None:
        self.storage_service = storage_service
        self.schema_manager = FingerMonitoringSchemaManager()

    @staticmethod
    def monitoring_root(data_root: Path) -> Path:
        return Path(data_root) / FINGER_MONITORING_RELATIVE_ROOT

    @classmethod
    def database_path(cls, data_root: Path) -> Path:
        return cls.monitoring_root(data_root) / "database" / FINGER_MONITORING_DATABASE_FILENAME

    def _data_root(self) -> Path:
        status = self.storage_service.resolve_status()
        root = getattr(status, "data_root", None)
        if root is None:
            raise RuntimeError("Data Root aktif belum tersedia.")
        return Path(root)

    def selected_data_root(self) -> Path:
        """Check the current pointer cheaply; full validation occurs on initialization."""
        path_reader = getattr(self.storage_service, "data_root_path", None)
        return Path(path_reader()) if path_reader is not None else self._data_root()

    def resolve_status(self) -> FingerMonitoringStorageStatus:
        try:
            root = self._data_root()
        except Exception as exc:
            return FingerMonitoringStorageStatus(None, None, None, False, False, "Data Root tidak tersedia", error=str(exc))
        monitoring_root = self.monitoring_root(root)
        database = self.database_path(root)
        if not database.is_file():
            return FingerMonitoringStorageStatus(root, monitoring_root, database, False, False, "Belum tersedia")
        try:
            version = self.schema_manager.validate(database)
            return FingerMonitoringStorageStatus(root, monitoring_root, database, True, True, "Siap", version, database.stat().st_size)
        except (OSError, sqlite3.Error, ValueError) as exc:
            return FingerMonitoringStorageStatus(root, monitoring_root, database, True, False, "Tidak valid", error=str(exc))

    def initialize(self) -> FingerMonitoringStorageStatus:
        """Create the dedicated tree on explicit module initialization only."""
        root = self._data_root()
        monitoring_root = self.monitoring_root(root)
        database = self.database_path(root)
        if database.exists():
            # Validation/migration happens before any mutation; a foreign or corrupt
            # database is never replaced automatically.
            self.schema_manager.migrate_to_current(database)
        else:
            for name in FINGER_MONITORING_DIRECTORIES:
                (monitoring_root / name).mkdir(parents=True, exist_ok=True)
            self.schema_manager.initialize(database)
        status = self.resolve_status()
        if not status.database_valid:
            raise RuntimeError(status.error or "Database Finger Monitoring tidak valid.")
        return status
