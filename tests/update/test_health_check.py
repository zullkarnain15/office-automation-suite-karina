from __future__ import annotations

import json
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import SCHEMA_VERSION
from shared.database.schema_manager import SchemaManager
from shared.storage.path_resolver import resolve_storage_layout
from shared.update.health_check import PostUpdateHealthCheck
from shared.update.transaction_store import UpdateTransactionStore
from updater.main import wait_for_health_marker


def test_wrong_health_check_transaction_id_rejected(tmp_path: Path) -> None:
    transaction = tmp_path / "data" / "update" / "transactions" / "tx" / "transaction.json"
    transaction.parent.mkdir(parents=True)
    marker = transaction.parent / "healthcheck_success.json"
    marker.write_text(
        json.dumps(
            {
                "transaction_id": "wrong",
                "status": "SUCCESS",
                "application_version": "1.1.0",
                "checks": {"application_version": True},
            }
        ),
        encoding="utf-8",
    )
    assert not wait_for_health_marker(transaction, "tx", "1.1.0", 0.1)


def test_wrong_application_version_rejected(tmp_path: Path) -> None:
    transaction = tmp_path / "data" / "update" / "transactions" / "tx" / "transaction.json"
    transaction.parent.mkdir(parents=True)
    marker = transaction.parent / "healthcheck_success.json"
    marker.write_text(
        json.dumps(
            {
                "transaction_id": "tx",
                "status": "SUCCESS",
                "application_version": "1.0.0",
                "checks": {"application_version": True},
            }
        ),
        encoding="utf-8",
    )
    assert not wait_for_health_marker(transaction, "tx", "1.1.0", 0.1)


def test_post_update_health_check_migrates_schema2_and_validates_database(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    layout = resolve_storage_layout(data_root)
    layout.database_root.mkdir(parents=True)
    layout.backup_root.mkdir(parents=True)
    SchemaManager().initialize_database(layout.database_path, "1.0.0")
    with SQLiteConnectionFactory().connect(layout.database_path) as connection:
        connection.execute("DROP TABLE att_data_repair_settings")
        connection.execute(
            """
            INSERT INTO global_settings (
                global_settings_id,
                output_root,
                period_start,
                period_end,
                updated_at,
                updated_by
            ) VALUES (1, ?, NULL, NULL, CURRENT_TIMESTAMP, 'Production Test')
            """,
            (r"C:\\ProductionData\\Output",),
        )
        connection.execute(
            "UPDATE database_metadata SET schema_version = 2 WHERE metadata_id = 1"
        )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()

    app_root = tmp_path / "app"
    app_root.mkdir()
    staging = data_root / "update" / "staging" / "v1.1.0"
    (staging / "application").mkdir(parents=True)
    transaction = UpdateTransactionStore(data_root).create(
        current_version="1.0.0",
        target_version="1.1.0",
        package_path=tmp_path / "package.zip",
        package_sha256="abc",
        staging_path=staging,
        application_root=app_root,
        database_backup_path=layout.backup_root / "pre_update.db",
        entry_executable="OAS-K.exe",
    )

    result = PostUpdateHealthCheck(application_version="1.1.0").run(
        transaction.transaction_path,
        create_ui_shell=False,
    )

    assert result.status == "SUCCESS"
    assert result.database_schema_version == SCHEMA_VERSION
    assert all(result.checks.values())
    with SQLiteConnectionFactory().connect(
        layout.database_path,
        read_only=True,
    ) as connection:
        schema_version = connection.execute(
            "SELECT schema_version FROM database_metadata WHERE metadata_id = 1"
        ).fetchone()[0]
        settings_count = connection.execute(
            "SELECT COUNT(*) FROM att_data_repair_settings"
        ).fetchone()[0]
        preserved_output_root = connection.execute(
            "SELECT output_root FROM global_settings WHERE global_settings_id = 1"
        ).fetchone()[0]
    assert schema_version == SCHEMA_VERSION
    assert settings_count == 1
    assert preserved_output_root == r"C:\\ProductionData\\Output"
    assert list(layout.backup_root.glob("OAS-K_before_schema_v4_*.db"))
