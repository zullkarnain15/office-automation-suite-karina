"""Import Existing Database and Reset to Default tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.database import REQUIRED_TABLES, SchemaManager
from shared.recovery import (
    ImportDatabaseRequest,
    ImportDatabaseService,
    ResetDatabaseRequest,
    ResetService,
)
from shared.recovery.audit_service import sha256_file
from shared.storage.path_resolver import resolve_storage_layout


def _version(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT application_version FROM database_metadata WHERE metadata_id=1"
        ).fetchone()[0]


def test_import_existing_database_succeeds(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(candidate_database, data_root, confirm=True)
    )
    assert result.success
    assert _version(result.active_database) == "db4-candidate"


def test_imported_source_not_activated_directly(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(candidate_database, data_root, confirm=True)
    )
    expected = resolve_storage_layout(data_root).database_path
    assert result.active_database.resolve() == expected.resolve()
    assert result.active_database.resolve() != candidate_database.resolve()


def test_import_source_not_deleted(
    data_root: Path,
    candidate_database: Path,
) -> None:
    before = sha256_file(candidate_database)
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(candidate_database, data_root, confirm=True)
    )
    assert result.success and candidate_database.is_file()
    assert sha256_file(candidate_database) == before


def test_import_incompatible_schema_rejected(
    data_root: Path,
    tmp_path: Path,
) -> None:
    incompatible = tmp_path / "schema5.db"
    SchemaManager().initialize_database(incompatible, "future")
    with sqlite3.connect(incompatible) as connection:
        connection.execute(
            "UPDATE database_metadata SET schema_version=5 WHERE metadata_id=1"
        )
        connection.execute("PRAGMA user_version=5")
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(incompatible, data_root, confirm=True)
    )
    assert not result.success
    assert _version(result.active_database) == "db4-active"


def test_import_same_source_rejected(data_root: Path) -> None:
    active = resolve_storage_layout(data_root).database_path
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(active, data_root, confirm=True)
    )
    assert not result.success
    assert "already the active" in result.errors[0]


def test_import_requires_confirmation(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(candidate_database, data_root, confirm=False)
    )
    assert not result.success


def test_import_creates_preoperation_backup(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = ImportDatabaseService().import_database(
        ImportDatabaseRequest(candidate_database, data_root, confirm=True)
    )
    assert result.pre_operation_backup is not None
    assert _version(result.pre_operation_backup) == "db4-active"


def test_reset_default_succeeds(data_root: Path) -> None:
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    assert result.success
    assert _version(result.active_database) == "db4-reset"


def test_reset_requires_confirmation(data_root: Path) -> None:
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=False)
    )
    assert not result.success
    assert _version(result.active_database) == "db4-active"


def test_global_settings_empty_after_reset(data_root: Path) -> None:
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    assert result.success, result.errors
    with sqlite3.connect(result.active_database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM global_settings"
        ).fetchone()[0]
    assert count == 0


def test_recorder_profiles_preserved_default(data_root: Path) -> None:
    profile = (
        resolve_storage_layout(data_root).hris_recorder_profiles_root
        / "profile.json"
    )
    profile.write_text('{"steps": []}', encoding="utf-8")
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    assert result.success and profile.is_file()
    assert result.recorder_profiles_preserved


def test_recorder_profiles_removed_only_when_explicit(data_root: Path) -> None:
    profile = (
        resolve_storage_layout(data_root).hris_recorder_profiles_root
        / "profile.json"
    )
    profile.write_text('{"steps": []}', encoding="utf-8")
    result = ResetService().reset(
        ResetDatabaseRequest(
            data_root,
            "db4-reset",
            confirm=True,
            preserve_recorder_profiles=False,
        )
    )
    assert result.success
    assert not profile.exists()
    assert not result.recorder_profiles_preserved


def test_old_database_available_in_backup(data_root: Path) -> None:
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    assert result.pre_operation_backup is not None
    assert result.pre_operation_backup.is_file()
    assert _version(result.pre_operation_backup) == "db4-active"


def test_reset_database_has_required_tables(data_root: Path) -> None:
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    with sqlite3.connect(result.active_database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert tables == set(REQUIRED_TABLES)
    assert len(tables) == len(REQUIRED_TABLES)


def test_reset_history_starts_fresh_except_operation(data_root: Path) -> None:
    active = resolve_storage_layout(data_root).database_path
    connection = sqlite3.connect(active)
    try:
        connection.execute(
            "INSERT INTO backup_history "
            "(action_type, source_path, started_at, status) "
            "VALUES ('BACKUP', 'old', '2026-01-01', 'SUCCESS')"
        )
        connection.commit()
    finally:
        connection.close()
    result = ResetService().reset(
        ResetDatabaseRequest(data_root, "db4-reset", confirm=True)
    )
    assert result.success, result.errors
    with sqlite3.connect(result.active_database) as connection:
        rows = connection.execute(
            "SELECT action_type FROM backup_history"
        ).fetchall()
    assert rows == [("RESET_TO_DEFAULT",)]
