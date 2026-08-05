"""Candidate validation and active database backup coverage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.database import SCHEMA_VERSION, BackupManager, REQUIRED_TABLES
from shared.recovery import (
    BackupReason,
    CandidateValidator,
    DatabaseBackupRequest,
    DatabaseBackupService,
)
from shared.storage.path_resolver import resolve_storage_layout


def test_candidate_valid(data_root: Path) -> None:
    result = CandidateValidator().validate(
        resolve_storage_layout(data_root).database_path
    )
    assert result.can_activate
    assert result.integrity_ok and result.foreign_keys_ok
    assert result.schema_version == SCHEMA_VERSION


def test_candidate_missing(tmp_path: Path) -> None:
    result = CandidateValidator().validate(tmp_path / "missing.db")
    assert not result.exists
    assert not result.can_activate


def test_candidate_non_sqlite(tmp_path: Path) -> None:
    path = tmp_path / "invalid.db"
    path.write_text("not sqlite", encoding="utf-8")
    result = CandidateValidator().validate(path)
    assert not result.sqlite_valid
    assert not result.can_activate


def test_candidate_required_tables(data_root: Path) -> None:
    result = CandidateValidator().validate(
        resolve_storage_layout(data_root).database_path
    )
    assert result.required_tables_ok
    assert len(REQUIRED_TABLES) == 25


def test_backup_database_succeeds(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    result = DatabaseBackupService().backup(
        DatabaseBackupRequest(
            layout.database_path,
            layout.backup_root,
            BackupReason.MANUAL,
        )
    )
    assert result.success
    assert result.backup_path is not None and result.backup_path.is_file()
    assert result.sha256 and result.file_size > 0


def test_backup_uses_sqlite_backup_api(
    data_root: Path,
    monkeypatch,
) -> None:
    calls = 0
    original = BackupManager.create_backup

    def tracked(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(BackupManager, "create_backup", tracked)
    layout = resolve_storage_layout(data_root)
    result = DatabaseBackupService().backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    assert result.success and calls == 1


def test_backup_is_valid(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    result = DatabaseBackupService().backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    assert result.backup_path is not None
    assert CandidateValidator().validate(result.backup_path).can_activate


def test_backup_history_recorded(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    result = DatabaseBackupService().backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    with sqlite3.connect(layout.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM backup_history WHERE action_type='BACKUP'"
        ).fetchone()[0]
    assert result.history_id is not None
    assert count == 1


def test_backup_name_collision_safe(data_root: Path, monkeypatch) -> None:
    layout = resolve_storage_layout(data_root)
    monkeypatch.setattr(
        BackupManager,
        "suggested_filename",
        staticmethod(lambda timestamp=None: "OAS-K_fixed.db"),
    )
    service = DatabaseBackupService()
    first = service.backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    second = service.backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    assert first.success and second.success
    assert first.backup_path != second.backup_path


def test_backup_keeps_business_data(data_root: Path, factory) -> None:
    layout = resolve_storage_layout(data_root)
    with factory.connect(layout.database_path) as connection:
        connection.execute(
            "INSERT INTO application_preferences "
            "(preference_key, preference_value, value_type, updated_at) "
            "VALUES ('marker', 'kept', 'TEXT', '2026-01-01T00:00:00')"
        )
    result = DatabaseBackupService().backup(
        DatabaseBackupRequest(layout.database_path, layout.backup_root)
    )
    with factory.connect(layout.database_path, read_only=True) as connection:
        value = connection.execute(
            "SELECT preference_value FROM application_preferences WHERE preference_key='marker'"
        ).fetchone()[0]
    assert result.success and value == "kept"
