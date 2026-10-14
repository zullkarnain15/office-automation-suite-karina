"""Portable analytics database validation, export, import, and rollback."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.attendance_ot import (
    ANALYTICS_SCHEMA_VERSION,
    AttendanceOTDatabaseTransferService,
    AttendanceOTStorageService,
)


class _CoreStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve_status(self):
        return SimpleNamespace(
            data_root=self.root,
            database_valid=True,
        )


@pytest.fixture
def transfer_environment(tmp_path: Path):
    root = tmp_path / "Data"
    root.mkdir()
    storage = AttendanceOTStorageService(_CoreStorage(root))
    active = storage.initialize().database_path
    assert active is not None
    transfer = AttendanceOTDatabaseTransferService(storage)
    return storage, transfer, active


def test_validate_rejects_non_sqlite_file(
    transfer_environment, tmp_path: Path
) -> None:
    _storage, transfer, _active = transfer_environment
    candidate = tmp_path / "not-a-database.db"
    candidate.write_bytes(b"not sqlite")

    result = transfer.validate_candidate(candidate)

    assert not result.is_valid
    assert result.errors


def test_export_is_verified_and_import_atomically_replaces_active_database(
    transfer_environment, tmp_path: Path
) -> None:
    _storage, transfer, active = transfer_environment
    portable = tmp_path / "portable.bak"

    exported = transfer.export_verified(portable)
    with sqlite3.connect(active) as connection:
        connection.execute("CREATE TABLE local_only(value TEXT)")
        connection.execute("INSERT INTO local_only VALUES ('old-active')")

    imported = transfer.import_candidate(portable)

    assert exported.destination == portable.resolve()
    assert len(exported.sha256) == 64
    assert imported.active_database == active.resolve()
    assert imported.schema_version == ANALYTICS_SCHEMA_VERSION
    assert imported.rebuilt_analytics
    assert imported.previous_database_backup is not None
    assert imported.previous_database_backup.is_file()
    assert imported.validation.is_valid
    with sqlite3.connect(active) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name='local_only'"
        ).fetchone()[0] == 0


def test_newer_schema_is_rejected(
    transfer_environment, tmp_path: Path
) -> None:
    _storage, transfer, _active = transfer_environment
    candidate = tmp_path / "future.db"
    transfer.export_verified(candidate)
    with sqlite3.connect(candidate) as connection:
        connection.execute(
            "UPDATE analytics_metadata SET schema_version=? WHERE metadata_id=1",
            (ANALYTICS_SCHEMA_VERSION + 1,),
        )
        connection.execute(f"PRAGMA user_version={ANALYTICS_SCHEMA_VERSION + 1}")

    result = transfer.validate_candidate(candidate)

    assert not result.is_valid
    assert any("lebih baru" in error for error in result.errors)


def test_supported_old_schema_is_migrated_only_in_staging(
    transfer_environment, tmp_path: Path
) -> None:
    _storage, transfer, _active = transfer_environment
    candidate = tmp_path / "schema-v1.db"
    with sqlite3.connect(candidate) as connection:
        connection.execute(
            """
            CREATE TABLE analytics_metadata (
                metadata_id INTEGER PRIMARY KEY CHECK (metadata_id=1),
                database_uuid TEXT NOT NULL UNIQUE,
                schema_version INTEGER NOT NULL,
                initialized_at TEXT NOT NULL,
                last_migrated_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO analytics_metadata VALUES "
            "(1, 'portable-v1', 1, '2026-01-01T00:00:00', NULL)"
        )
        connection.execute("PRAGMA user_version=1")

    imported = transfer.import_candidate(candidate)

    assert imported.migrated
    assert imported.source_schema_version == 1
    assert imported.schema_version == ANALYTICS_SCHEMA_VERSION
    assert imported.validation.is_valid
    with sqlite3.connect(candidate) as connection:
        assert connection.execute(
            "SELECT schema_version FROM analytics_metadata"
        ).fetchone()[0] == 1


def test_failed_post_import_health_check_rolls_back_active_database(
    transfer_environment, tmp_path: Path, monkeypatch
) -> None:
    _storage, transfer, active = transfer_environment
    candidate = tmp_path / "candidate.bak"
    transfer.export_verified(candidate)
    with sqlite3.connect(active) as connection:
        connection.execute("CREATE TABLE rollback_marker(value TEXT)")
        connection.execute("INSERT INTO rollback_marker VALUES ('preserved')")

    monkeypatch.setattr(
        transfer,
        "_post_import_health_check",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("health failed")),
    )

    with pytest.raises(RuntimeError, match="health failed"):
        transfer.import_candidate(candidate)

    with sqlite3.connect(active) as connection:
        assert connection.execute(
            "SELECT value FROM rollback_marker"
        ).fetchone()[0] == "preserved"
