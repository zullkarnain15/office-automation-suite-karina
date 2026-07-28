"""Schema, connection, migration, and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import shared.database as database_package
from shared.database import (
    DatabaseInitializationError,
    DatabaseValidator,
    MigrationManager,
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    SQLiteConnectionFactory,
    SchemaManager,
    SchemaMismatchError,
)
from shared.database.repositories import MetadataRepository


def test_database_package_imports_without_side_effects() -> None:
    assert database_package.SCHEMA_VERSION == 2
    assert len(database_package.REQUIRED_TABLES) == 24


def test_initialize_database_creates_exact_schema_and_metadata(
    database_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(
        database_path,
        read_only=True,
    ) as connection:
        table_rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        metadata = MetadataRepository(connection).get_metadata()
        user_version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

    assert {str(row[0]) for row in table_rows} == set(REQUIRED_TABLES)
    assert len(table_rows) == 24
    assert metadata.schema_version == SCHEMA_VERSION
    assert metadata.application_version == "test-1.0.0"
    assert user_version == SCHEMA_VERSION


def test_connection_enables_required_pragmas(database_path: Path) -> None:
    with SQLiteConnectionFactory().connect(
        database_path,
        read_only=True,
    ) as connection:
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        busy_timeout = connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]
    with SQLiteConnectionFactory().connect(database_path) as connection:
        journal_mode = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]
        synchronous = connection.execute(
            "PRAGMA synchronous"
        ).fetchone()[0]

    assert foreign_keys == 1
    assert busy_timeout == 5_000
    assert str(journal_mode).upper() == "DELETE"
    assert synchronous == 2


def test_factory_creates_parent_only_when_requested(tmp_path: Path) -> None:
    nested_path = tmp_path / "missing" / "database.db"
    factory = SQLiteConnectionFactory()

    with pytest.raises(FileNotFoundError):
        with factory.connect(nested_path):
            pass

    with factory.connect(nested_path, create_parent=True) as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    assert nested_path.is_file()


def test_second_initialization_preserves_existing_data(
    database_path: Path,
) -> None:
    factory = SQLiteConnectionFactory()
    with factory.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO application_preferences (
                preference_key,
                preference_value,
                value_type,
                updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("theme", "dark", "TEXT", "2026-07-20T12:00:00"),
        )

    metadata = SchemaManager().initialize_database(
        database_path,
        application_version="ignored-on-existing",
    )
    with factory.connect(database_path, read_only=True) as connection:
        value = connection.execute(
            """
            SELECT preference_value
            FROM application_preferences
            WHERE preference_key = ?
            """,
            ("theme",),
        ).fetchone()[0]

    assert value == "dark"
    assert metadata.application_version == "test-1.0.0"


def test_failed_initialization_rolls_back_schema_and_metadata(
    tmp_path: Path,
) -> None:
    invalid_schema = tmp_path / "invalid-v1.sql"
    invalid_schema.write_text(
        """
        CREATE TABLE first_table (item_id INTEGER PRIMARY KEY);
        CREATE TABL broken_statement (item_id INTEGER);
        """,
        encoding="utf-8",
    )
    database_path = tmp_path / "failed.db"
    manager = SchemaManager()
    manager.schema_file = invalid_schema

    with pytest.raises(DatabaseInitializationError):
        manager.initialize_database(database_path, "test-1.0.0")

    assert manager.is_initialized(database_path) is False
    with SQLiteConnectionFactory().connect(
        database_path,
        read_only=True,
    ) as connection:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
    assert tables == []


def test_schema_mismatch_raises_without_reset(
    database_path: Path,
) -> None:
    factory = SQLiteConnectionFactory()
    with factory.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE database_metadata
            SET schema_version = 3, updated_at = ?
            WHERE metadata_id = 1
            """,
            ("2026-07-20T12:00:00",),
        )
        connection.execute("PRAGMA user_version = 3")

    with pytest.raises(SchemaMismatchError, match="newer"):
        SchemaManager().ensure_compatible_schema(database_path)

    with factory.connect(database_path, read_only=True) as connection:
        table_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()[0]
    assert table_count == 24


def test_migration_manager_is_noop_for_current_schema(
    database_path: Path,
) -> None:
    manager = MigrationManager(database_path)

    assert manager.get_current_version() == 2
    assert manager.get_target_version() == 2
    assert manager.requires_migration() is False
    assert manager.migrate() == 2


def test_migration_v1_to_v2_adds_payroll_period_without_data_loss(
    tmp_path: Path,
) -> None:
    path = tmp_path / "schema-v1.db"
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
            ) VALUES (1, 'migration-test', 1, 'test', '2026-07-28', '2026-07-28')
            """
        )
        connection.execute(
            """
            INSERT INTO outlook_settings (
                outlook_settings_id, mailbox_smtp, updated_at
            ) VALUES (1, 'karina.hr.1@oto.co.id', '2026-07-28')
            """
        )
        connection.execute("PRAGMA user_version = 1")

    migration = MigrationManager(path)
    assert migration.requires_migration()
    assert migration.migrate() == 2

    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(outlook_settings)"
            )
        }
        row = connection.execute(
            "SELECT mailbox_smtp, payroll_period FROM outlook_settings"
        ).fetchone()
    assert "payroll_period" in columns
    assert row["mailbox_smtp"] == "karina.hr.1@oto.co.id"
    assert row["payroll_period"] is None


def test_validator_reports_integrity_and_unconfigured_global_settings(
    database_path: Path,
) -> None:
    result = DatabaseValidator().validate(database_path)

    assert result.is_valid is True
    assert result.integrity_ok is True
    assert result.foreign_keys_ok is True
    assert result.schema_version == 2
    assert result.missing_tables == ()
    assert result.missing_indexes == ()
    assert "Global settings are not configured yet." in result.warnings


def test_validator_detects_missing_required_table(
    database_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        connection.execute("DROP TABLE comparison_settings")

    result = DatabaseValidator().validate(database_path)

    assert result.is_valid is False
    assert result.missing_tables == ("comparison_settings",)
    assert any("Missing required tables" in item for item in result.errors)


def test_validator_detects_missing_required_index(
    database_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        connection.execute(
            "DROP INDEX idx_job_history_module_started"
        )

    result = DatabaseValidator().validate(database_path)

    assert result.is_valid is False
    assert result.missing_indexes == (
        "idx_job_history_module_started",
    )


def test_non_sqlite_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "not-a-database.db"
    path.write_text("not sqlite", encoding="utf-8")

    result = DatabaseValidator().validate(path)

    assert result.is_valid is False
    assert result.sqlite_header_ok is False
    assert any("SQLite header" in error for error in result.errors)


def test_schema_file_uses_no_blob_columns() -> None:
    schema_path = (
        Path(database_package.__file__).parent / "schema" / "v1.sql"
    )
    schema = schema_path.read_text(encoding="utf-8")

    assert " BLOB" not in schema.upper()
    assert "CREATE TABLE module_settings" not in schema
    assert "CREATE TABLE utilities_settings" not in schema
