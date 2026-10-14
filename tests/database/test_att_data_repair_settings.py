from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shared.database import (
    DatabaseValidator,
    MigrationManager,
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    SQLiteConnectionFactory,
    SchemaManager,
)


def test_schema_v4_contains_att_data_repair_singleton_defaults(
    database_path: Path,
) -> None:
    assert SCHEMA_VERSION == 4
    assert "att_data_repair_settings" in REQUIRED_TABLES

    with SQLiteConnectionFactory().connect(database_path, read_only=True) as connection:
        row = connection.execute(
            "SELECT * FROM att_data_repair_settings "
            "WHERE att_data_repair_settings_id = 1"
        ).fetchone()
        metadata = connection.execute(
            "SELECT schema_version FROM database_metadata WHERE metadata_id = 1"
        ).fetchone()

    assert metadata["schema_version"] == 4
    assert row["enabled"] == 1
    assert row["minimum_duration_minutes"] == 61
    assert row["weekday_default_in"] == "09:30"
    assert row["weekday_default_out"] == "17:00"
    assert row["saturday_default_out"] == "12:05"
    assert row["saturday_missing_out_default"] == "11:00"
    assert row["sunday_invalid_default_out"] == "12:05"
    assert row["midnight_time_out_default"] == "23:59"
    assert row["txt_max_rows"] == 10000
    assert row["generate_txt"] == 1
    assert row["generate_excel_report"] == 1
    assert row["use_global_period"] == 1
    assert row["use_global_output"] == 1
    assert DatabaseValidator().validate(database_path).is_valid


def test_att_data_repair_sqlite_constraints(database_path: Path) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE att_data_repair_settings SET enabled = 2 "
                "WHERE att_data_repair_settings_id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE att_data_repair_settings "
                "SET weekday_default_in = '18:00', weekday_default_out = '09:00' "
                "WHERE att_data_repair_settings_id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE att_data_repair_settings "
                "SET generate_txt = 0, generate_excel_report = 0 "
                "WHERE att_data_repair_settings_id = 1"
            )


def test_migration_v2_to_v4_adds_settings_without_data_loss(tmp_path: Path) -> None:
    database = tmp_path / "v2.db"
    manager = SchemaManager()
    with SQLiteConnectionFactory().connect(database, create_parent=True) as connection:
        schema = manager.schema_file.read_text(encoding="utf-8")
        for statement in manager._sql_statements(schema):
            connection.execute(statement)
        migration_v2 = manager.migrations_path / "v1_to_v2.sql"
        for statement in manager._sql_statements(migration_v2.read_text(encoding="utf-8")):
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO database_metadata (
                metadata_id, database_uuid, schema_version,
                application_version, created_at, updated_at
            ) VALUES (1, 'v2-test', 2, 'test', '2026-08-03', '2026-08-03')
            """
        )
        connection.execute(
            """
            INSERT INTO outlook_settings (
                outlook_settings_id, mailbox_smtp, updated_at, payroll_period
            ) VALUES (1, 'karina@example.com', '2026-08-03', '07-2026')
            """
        )
        connection.execute("PRAGMA user_version = 2")

    assert MigrationManager(database).migrate() == 4

    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        outlook = connection.execute(
            "SELECT mailbox_smtp, payroll_period FROM outlook_settings"
        ).fetchone()
        att = connection.execute(
            "SELECT minimum_duration_minutes, txt_max_rows, "
            "saturday_missing_out_default, midnight_time_out_default "
            "FROM att_data_repair_settings"
        ).fetchone()
    assert tuple(outlook) == ("karina@example.com", "07-2026")
    assert tuple(att) == (61, 10000, "11:00", "23:59")


def test_migration_v3_to_v4_preserves_existing_att_data_repair_settings(
    tmp_path: Path,
) -> None:
    database = tmp_path / "v3.db"
    manager = SchemaManager()
    with SQLiteConnectionFactory().connect(database, create_parent=True) as connection:
        for statement in manager._sql_statements(
            manager.schema_file.read_text(encoding="utf-8")
        ):
            connection.execute(statement)
        for migration_name in ("v1_to_v2.sql", "v2_to_v3.sql"):
            migration = manager.migrations_path / migration_name
            for statement in manager._sql_statements(
                migration.read_text(encoding="utf-8")
            ):
                connection.execute(statement)
        connection.execute(
            """
            INSERT INTO database_metadata (
                metadata_id, database_uuid, schema_version,
                application_version, created_at, updated_at
            ) VALUES (1, 'v3-test', 3, 'test', '2026-08-03', '2026-08-03')
            """
        )
        connection.execute(
            """
            UPDATE att_data_repair_settings
            SET saturday_default_out = '12:30', updated_by = 'Existing User'
            WHERE att_data_repair_settings_id = 1
            """
        )
        connection.execute("PRAGMA user_version = 3")

    assert MigrationManager(database).migrate() == 4

    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        row = connection.execute(
            """
            SELECT saturday_default_out, updated_by,
                   saturday_missing_out_default, midnight_time_out_default
            FROM att_data_repair_settings
            WHERE att_data_repair_settings_id = 1
            """
        ).fetchone()
    assert tuple(row) == ("12:30", "Existing User", "11:00", "23:59")
