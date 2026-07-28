from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import (
    DatabaseValidator,
    MigrationError,
    SchemaManager,
    SQLiteConnectionFactory,
    StartupDatabaseMigrationError,
    StartupDatabaseMigrator,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.services.storage_ui_service import StorageUIService


def _create_schema_v1_database(path: Path) -> None:
    manager = SchemaManager()
    with SQLiteConnectionFactory().connect(
        path,
        create_parent=True,
    ) as connection:
        schema = manager.schema_file.read_text(encoding="utf-8")
        for statement in manager._sql_statements(schema):
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO database_metadata (
                metadata_id, database_uuid, schema_version,
                application_version, created_at, updated_at
            ) VALUES (
                1, 'production-v1', 1,
                'production-old', '2026-07-01', '2026-07-01'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO outlook_settings (
                outlook_settings_id, mailbox_smtp,
                resubmit_deadline, updated_at
            ) VALUES (
                1, 'karina.hr.1@oto.co.id',
                'Production deadline', '2026-07-01'
            )
            """
        )
        connection.execute("PRAGMA user_version = 1")


def test_startup_migration_backs_up_and_preserves_production_data(
    tmp_path: Path,
) -> None:
    database = tmp_path / "database" / "OAS-K.db"
    backup_root = tmp_path / "backup"
    _create_schema_v1_database(database)
    messages: list[str] = []

    result = StartupDatabaseMigrator().ensure_current(
        database,
        backup_root,
        progress=messages.append,
    )

    assert result.status == "MIGRATED"
    assert (result.previous_version, result.current_version) == (1, 2)
    assert result.backup_path is not None and result.backup_path.is_file()
    assert result.backup_path.parent == backup_root
    assert result.backup_path.name.startswith("OAS-K_before_schema_v2_")
    assert DatabaseValidator(expected_version=1).validate(
        result.backup_path
    ).is_valid
    assert DatabaseValidator().validate(database).is_valid
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        row = connection.execute(
            """
            SELECT mailbox_smtp, resubmit_deadline, payroll_period
            FROM outlook_settings
            WHERE outlook_settings_id = 1
            """
        ).fetchone()
    assert tuple(row) == (
        "karina.hr.1@oto.co.id",
        "Production deadline",
        None,
    )
    assert any("Mencadangkan" in message for message in messages)
    assert any("v1 ke v2" in message for message in messages)


def test_current_database_is_noop_and_does_not_create_backup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "database" / "OAS-K.db"
    SchemaManager().initialize_database(
        database,
        "current",
        create_parent=True,
    )
    backup_root = tmp_path / "backup"

    result = StartupDatabaseMigrator().ensure_current(
        database,
        backup_root,
    )

    assert result.status == "CURRENT"
    assert result.backup_path is None
    assert not backup_root.exists()


def test_failed_migration_keeps_v1_source_and_valid_backup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "database" / "OAS-K.db"
    backup_root = tmp_path / "backup"
    _create_schema_v1_database(database)

    def fail_migration(_self):
        raise MigrationError("simulated migration failure")

    monkeypatch.setattr(
        "shared.database.startup_migration.MigrationManager.migrate",
        fail_migration,
    )

    with pytest.raises(
        StartupDatabaseMigrationError,
        match="simulated migration failure",
    ):
        StartupDatabaseMigrator().ensure_current(database, backup_root)

    backups = tuple(backup_root.glob("*.db"))
    assert len(backups) == 1
    assert DatabaseValidator(expected_version=1).validate(database).is_valid
    assert DatabaseValidator(expected_version=1).validate(backups[0]).is_valid


def test_storage_service_migrates_registered_v1_database(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "Data"
    layout = resolve_storage_layout(data_root)
    _create_schema_v1_database(layout.database_path)
    backend = FakeRegistryBackend()
    registry = StorageRegistryService(backend)
    registry.write_storage_pointer(data_root, layout.database_path)
    service = StorageUIService(
        registry,
        application_version="new-app",
        default_data_root=tmp_path / "unused",
    )

    result = service.prepare_startup_database()

    assert result.status == "MIGRATED"
    assert result.database_path == layout.database_path
    assert result.backup_path is not None
    assert result.backup_path.parent == layout.backup_root
