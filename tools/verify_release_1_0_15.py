"""Isolated release-gate verification for OAS-K 1.0.15."""

from __future__ import annotations

import gc
import importlib.util
import json
import logging
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE_VERIFIER = Path(__file__).with_name("verify_release_1_0_11.py")
VERSION = "1.0.15"
PREVIOUS_VERSION = "1.0.14"
CORE_SCHEMA = 4
PRODUCTION_ANALYTICS_SCHEMA = 5
TARGET_ANALYTICS_SCHEMA = 9


def _create_schema5_database(database: Path) -> None:
    from shared.attendance_ot.schema import AnalyticsSchemaManager

    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
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
            "(1, 'release-schema5', 1, '2026-09-30T00:00:00', NULL)"
        )
        connection.execute("PRAGMA user_version=1")

    manager = AnalyticsSchemaManager()
    manager._migrate_v1_to_v2(database)
    manager._migrate_v2_to_v3(database)
    manager._migrate_v3_to_v4(database)
    manager._migrate_v4_to_v5(database)

    with manager.factory.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO source_registry (
                source_id, source_type, source_path, filename, size_bytes,
                modified_time_ns, row_count, status, imported_at, fingerprint,
                error_detail, last_seen_at, created_at, updated_at
            ) VALUES (
                1, 'ATTENDANCE_OT', 'C:/production/attendance.xlsx',
                'attendance.xlsx', 2048, 123456789, 1, 'UNCHANGED',
                '2026-09-30T08:00:00', NULL, NULL, '2026-09-30T08:00:00',
                '2026-09-30T08:00:00', '2026-09-30T08:00:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO attendance_records (
                source_id, source_file, source_sheet, source_row, emplid,
                date_in, time_in, date_out, time_out, overtime_hour,
                overtime_minute, ot_amount, meal_ot_amount, location_descr,
                name, paylink
            ) VALUES (
                1, 'C:/production/attendance.xlsx', 'Imported Data', 2,
                'PROD-001', '2026-09-30', '08:00:00', '2026-09-30',
                '17:00:00', 1, 30, 150000, 25000, 'HEAD OFFICE',
                'Production Employee', 'PG-PROD'
            )
            """
        )


def _verify_schema5_to_schema9(package: Path, old_executable: Path) -> dict[str, object]:
    from shared.attendance_ot.schema import ANALYTICS_SCHEMA_VERSION
    from shared.attendance_ot.storage import AttendanceOTStorageService
    from shared.database.connection_factory import SQLiteConnectionFactory
    from shared.database.schema_manager import SchemaManager
    from shared.storage.path_resolver import resolve_storage_layout
    from shared.update import ApplicationUpdateService
    from shared.update.health_check import PostUpdateHealthCheck

    assert ANALYTICS_SCHEMA_VERSION == TARGET_ANALYTICS_SCHEMA
    temp_parent = ROOT / ".codex_tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="release_1_0_15_schema5_", dir=temp_parent
    ) as temp_name:
        smoke_root = Path(temp_name)
        app_root = smoke_root / "application"
        app_root.mkdir()
        shutil.copy2(old_executable, app_root / "OAS-K.exe")

        layout = resolve_storage_layout(smoke_root / "DataRoot")
        SchemaManager().initialize_database(
            layout.database_path, PREVIOUS_VERSION, create_parent=True
        )
        analytics_database = (
            layout.data_root
            / "analytics"
            / "attendance_ot"
            / "database"
            / "attendance_ot.db"
        )
        _create_schema5_database(analytics_database)

        service = ApplicationUpdateService()
        prepared = service.prepare_update(
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
        assert health.database_schema_version == CORE_SCHEMA

        core_storage = SimpleNamespace(
            resolve_status=lambda: SimpleNamespace(
                data_root=layout.data_root,
                database_valid=True,
            )
        )
        analytics = AttendanceOTStorageService(core_storage)
        migrated = analytics.initialize()
        assert migrated.database_valid
        assert migrated.schema_version == TARGET_ANALYTICS_SCHEMA

        backups = {
            version: tuple(
                analytics_database.parent.glob(f"attendance_ot.before-v{version}.*.bak")
            )
            for version in (6, 7, 8, 9)
        }
        assert all(len(paths) == 1 for paths in backups.values()), backups
        with SQLiteConnectionFactory().connect(
            backups[6][0], read_only=True
        ) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 5

        with SQLiteConnectionFactory().connect(
            analytics_database, read_only=True
        ) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
            row = connection.execute(
                """
                SELECT emplid, name, location_descr, paylink, ot_amount,
                       meal_ot_amount, job_title
                FROM attendance_records
                """
            ).fetchone()
            assert tuple(row) == (
                "PROD-001",
                "Production Employee",
                "HEAD OFFICE",
                "PG-PROD",
                150000.0,
                25000.0,
                None,
            )
            registry = connection.execute(
                """
                SELECT source_type, full_path, file_size, modified_time_ns,
                       last_imported, status
                FROM source_file_registry
                """
            ).fetchone()
            assert tuple(registry) == (
                "ATTENDANCE_OT",
                "C:/production/attendance.xlsx",
                2048,
                123456789,
                "2026-09-30T08:00:00",
                "UNCHANGED",
            )
        gc.collect()

    return {
        "production_attendance_ot_schema": PRODUCTION_ANALYTICS_SCHEMA,
        "attendance_ot_schema_to": TARGET_ANALYTICS_SCHEMA,
        "attendance_ot_migration_path": "5->6->7->8->9",
        "attendance_ot_backups_verified": True,
        "attendance_ot_data_preserved": True,
        "attendance_ot_registry_backfilled": True,
    }


def main() -> None:
    logging.disable(logging.CRITICAL)
    spec = importlib.util.spec_from_file_location(
        "oas_k_release_verifier_base", BASE_VERIFIER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Tidak dapat memuat verifier: {BASE_VERIFIER}")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.VERSION = VERSION
    verifier.PREVIOUS_VERSION = PREVIOUS_VERSION
    verifier.CORE_SCHEMA = CORE_SCHEMA
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
    analytics_report = _verify_schema5_to_schema9(package, old_executable)
    report_path = release / "verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(analytics_report)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
