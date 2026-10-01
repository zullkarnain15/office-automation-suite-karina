"""Sprint 1 contracts for Attendance & OT storage and preferences."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.attendance_ot import (
    ANALYTICS_SCHEMA_VERSION,
    AttendanceOTStorageService,
)
from shared.database import SCHEMA_VERSION, SchemaManager
from ui.services.database_settings_service import DatabaseSettingsService
from ui.services.protocols import AttendanceOTSourceDraft


class _CoreStorage:
    def __init__(self, root: Path | None) -> None:
        self.root = root

    def resolve_status(self):
        return SimpleNamespace(
            data_root=self.root,
            database_valid=self.root is not None,
        )


def test_analytics_storage_is_created_under_active_data_root(tmp_path: Path) -> None:
    root = tmp_path / "Data"
    root.mkdir()
    service = AttendanceOTStorageService(_CoreStorage(root))

    before = service.resolve_status()
    assert not before.database_exists
    result = service.initialize()

    expected_root = root / "analytics" / "attendance_ot"
    assert result.database_path == expected_root / "database" / "attendance_ot.db"
    assert result.database_valid
    assert result.schema_version == ANALYTICS_SCHEMA_VERSION
    for name in ("database", "cache", "export", "logs"):
        assert (expected_root / name).is_dir()


def test_analytics_initialization_is_idempotent_and_preserves_data(tmp_path: Path) -> None:
    root = tmp_path / "Data"
    root.mkdir()
    service = AttendanceOTStorageService(_CoreStorage(root))
    database = service.initialize().database_path
    assert database is not None
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE keep_me (value TEXT NOT NULL)")
        connection.execute("INSERT INTO keep_me VALUES ('existing')")

    service.initialize()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM keep_me").fetchone()[0] == "existing"


def test_existing_unknown_database_is_not_overwritten(tmp_path: Path) -> None:
    root = tmp_path / "Data"
    database = root / "analytics" / "attendance_ot" / "database" / "attendance_ot.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"existing-not-sqlite")
    service = AttendanceOTStorageService(_CoreStorage(root))

    with pytest.raises(RuntimeError, match="tidak diubah"):
        service.initialize()
    assert database.read_bytes() == b"existing-not-sqlite"


def test_nonempty_rollback_journal_is_reported_as_recovery_required(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Data"
    database = root / "analytics" / "attendance_ot" / "database" / "attendance_ot.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"incomplete-sqlite-state")
    Path(str(database) + "-journal").write_bytes(b"journal-state")

    status = AttendanceOTStorageService(_CoreStorage(root)).resolve_status()

    assert status.status == "Recovery required"
    assert "Repair ATTENDANCE & OT" in (status.error or "")


def test_repair_interrupted_transaction_preserves_pre_recovery_copy(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Data"
    root.mkdir()
    service = AttendanceOTStorageService(_CoreStorage(root))
    database = service.initialize().database_path
    assert database is not None
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=PERSIST")
        connection.execute("CREATE TABLE recovery_fixture(value TEXT)")
        connection.execute("INSERT INTO recovery_fixture VALUES ('safe')")
    journal = Path(str(database) + "-journal")
    assert journal.is_file() and journal.stat().st_size > 0

    result = service.repair_interrupted_transaction()

    assert Path(result["pre_recovery_copy"]).joinpath(database.name).is_file()
    assert Path(result["verified_backup"]).is_file()
    assert service.resolve_status().database_valid
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT value FROM recovery_fixture"
        ).fetchone()[0] == "safe"


def test_core_and_analytics_schema_versions_are_independent(tmp_path: Path) -> None:
    root = tmp_path / "Data"
    root.mkdir()
    core_database = root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core_database, "test", create_parent=True)
    analytics = AttendanceOTStorageService(_CoreStorage(root)).initialize()

    assert SchemaManager().get_schema_version(core_database) == SCHEMA_VERSION
    assert analytics.schema_version == ANALYTICS_SCHEMA_VERSION


def test_three_source_preferences_round_trip_in_core_preferences(tmp_path: Path) -> None:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "test")
    attendance = tmp_path / "attendance"
    employee = tmp_path / "employee"
    schedule = tmp_path / "schedule"
    for folder in (attendance, employee, schedule):
        folder.mkdir()
    service = DatabaseSettingsService()
    draft = AttendanceOTSourceDraft(
        str(attendance), str(employee), str(schedule)
    )

    saved = service.save_attendance_ot_source_preferences(database, draft)

    assert saved == draft
    assert service.load_attendance_ot_source_preferences(database) == draft


def test_attendance_ot_requires_an_active_data_root() -> None:
    service = AttendanceOTStorageService(_CoreStorage(None))
    assert service.resolve_status().status == "Data Root core belum siap"
    with pytest.raises(RuntimeError, match="Data Root aktif belum siap"):
        service.initialize()
