"""Isolated release-gate verification for OAS-K 1.0.18."""

from __future__ import annotations

import gc
import importlib.util
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE_VERIFIER = Path(__file__).with_name("verify_release_1_0_16.py")
VERSION = "1.0.18"
PREVIOUS_VERSION = "1.0.17"
CORE_SCHEMA = 4
PRODUCTION_ANALYTICS_SCHEMA = 9
TARGET_ANALYTICS_SCHEMA = 9
PRODUCTION_FINGER_SCHEMA = 6
TARGET_FINGER_SCHEMA = 6


def _database_dump(path: Path) -> tuple[str, ...]:
    from shared.database.connection_factory import SQLiteConnectionFactory

    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        return tuple(connection.iterdump())


def _verify_finger_schema6_preserved(
    package: Path,
    old_executable: Path,
) -> dict[str, object]:
    from shared.database.connection_factory import SQLiteConnectionFactory
    from shared.database.schema_manager import SchemaManager
    from shared.finger_monitoring.schema import FINGER_MONITORING_SCHEMA_VERSION
    from shared.finger_monitoring.storage import FingerMonitoringStorageService
    from shared.storage.path_resolver import resolve_storage_layout
    from shared.update import ApplicationUpdateService
    from shared.update.health_check import PostUpdateHealthCheck

    assert FINGER_MONITORING_SCHEMA_VERSION == TARGET_FINGER_SCHEMA
    temp_parent = ROOT / ".codex_tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="release_1_0_18_finger_schema6_",
        dir=temp_parent,
    ) as temp_name:
        smoke_root = Path(temp_name)
        app_root = smoke_root / "application"
        app_root.mkdir()
        shutil.copy2(old_executable, app_root / "OAS-K.exe")

        layout = resolve_storage_layout(smoke_root / "DataRoot")
        SchemaManager().initialize_database(
            layout.database_path,
            PREVIOUS_VERSION,
            create_parent=True,
        )
        core_storage = SimpleNamespace(
            resolve_status=lambda: SimpleNamespace(
                data_root=layout.data_root,
                database_path=layout.database_path,
                database_valid=True,
            )
        )
        monitoring = FingerMonitoringStorageService(core_storage)
        status = monitoring.initialize()
        monitoring_database = status.database_path
        assert monitoring_database is not None

        with SQLiteConnectionFactory().connect(monitoring_database) as connection:
            connection.execute(
                """
                INSERT INTO device_master(
                    unit, three_lc, branch_name, ip_address, device_model,
                    is_active, note, created_at, updated_at
                ) VALUES (
                    'UNIT-PROD', '3LC', 'Production Branch', '10.70.1.10',
                    'X1500', 1, 'preserve', CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                UPDATE monitoring_settings
                SET recipient_email='production@example.com',
                    backup_mdb_root='\\\\server\\backup\\MDB',
                    backup_mdb_exclusions='arsip*;archive*',
                    updated_at=CURRENT_TIMESTAMP
                WHERE settings_id=1
                """
            )
            connection.commit()

        baseline = _database_dump(monitoring_database)
        backups_before = {
            path.name
            for path in monitoring_database.parents[1].joinpath("backup").glob("*")
        }
        prepared = ApplicationUpdateService().prepare_update(
            package,
            current_version=PREVIOUS_VERSION,
            data_root=layout.data_root,
            application_root=app_root,
        )
        health = PostUpdateHealthCheck(application_version=VERSION).run(
            prepared.transaction_path,
            create_ui_shell=False,
        )
        assert health.status == "SUCCESS"
        assert monitoring.resolve_status().database_valid
        assert monitoring.resolve_status().schema_version == TARGET_FINGER_SCHEMA
        assert _database_dump(monitoring_database) == baseline
        assert {
            path.name
            for path in monitoring_database.parents[1].joinpath("backup").glob("*")
        } == backups_before
        with SQLiteConnectionFactory().connect(
            monitoring_database,
            read_only=True,
        ) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
            row = connection.execute(
                """
                SELECT unit, three_lc, branch_name, ip_address, note
                FROM device_master
                """
            ).fetchone()
            assert tuple(row) == (
                "UNIT-PROD",
                "3LC",
                "Production Branch",
                "10.70.1.10",
                "preserve",
            )
        gc.collect()

    return {
        "production_finger_monitoring_schema": PRODUCTION_FINGER_SCHEMA,
        "finger_monitoring_schema_to": TARGET_FINGER_SCHEMA,
        "finger_monitoring_migration_path": "6->6 (no migration)",
        "finger_monitoring_backup_required": False,
        "finger_monitoring_data_preserved": True,
    }


def main() -> None:
    logging.disable(logging.CRITICAL)
    spec = importlib.util.spec_from_file_location(
        "oas_k_release_verifier_1_0_16",
        BASE_VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Tidak dapat memuat verifier: {BASE_VERIFIER}")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.VERSION = VERSION
    verifier.PREVIOUS_VERSION = PREVIOUS_VERSION
    verifier.CORE_SCHEMA = CORE_SCHEMA
    verifier.PRODUCTION_ANALYTICS_SCHEMA = PRODUCTION_ANALYTICS_SCHEMA
    verifier.TARGET_ANALYTICS_SCHEMA = TARGET_ANALYTICS_SCHEMA
    verifier.main()

    release = ROOT / "dist" / "release" / f"v{VERSION}"
    package = release / f"OAS-K_Update_v{VERSION}.zip"
    old_executable = (
        ROOT
        / "dist"
        / "release"
        / f"v{PREVIOUS_VERSION}"
        / "application"
        / "OAS-K.exe"
    )
    finger_report = _verify_finger_schema6_preserved(package, old_executable)
    report_path = release / "verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(finger_report)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
