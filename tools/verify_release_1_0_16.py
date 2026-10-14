"""Isolated release-gate verification for OAS-K 1.0.16."""

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
BASE_VERIFIER = Path(__file__).with_name("verify_release_1_0_11.py")
VERSION = "1.0.16"
PREVIOUS_VERSION = "1.0.15"
CORE_SCHEMA = 4
PRODUCTION_ANALYTICS_SCHEMA = 9
TARGET_ANALYTICS_SCHEMA = 9


def _database_dump(path: Path) -> tuple[str, ...]:
    from shared.database.connection_factory import SQLiteConnectionFactory

    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        return tuple(connection.iterdump())


def _verify_schema9_preserved(package: Path, old_executable: Path) -> dict[str, object]:
    from PyInstaller.archive.readers import CArchiveReader

    from shared.attendance_ot.schema import ANALYTICS_SCHEMA_VERSION
    from shared.attendance_ot.storage import AttendanceOTStorageService
    from shared.database.connection_factory import SQLiteConnectionFactory
    from shared.database.schema_manager import SchemaManager
    from shared.storage.path_resolver import resolve_storage_layout
    from shared.update import ApplicationUpdateService
    from shared.update.health_check import PostUpdateHealthCheck

    assert ANALYTICS_SCHEMA_VERSION == TARGET_ANALYTICS_SCHEMA
    release_executable = (
        ROOT / "dist" / "release" / f"v{VERSION}" / "application" / "OAS-K.exe"
    )
    frozen = CArchiveReader(str(release_executable))
    assert any(
        "python_calamine" in name and name.casefold().endswith(".pyd")
        for name in frozen.toc
    ), "Native python-calamine extension is missing from the frozen executable"

    temp_parent = ROOT / ".codex_tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="release_1_0_16_schema9_", dir=temp_parent
    ) as temp_name:
        smoke_root = Path(temp_name)
        app_root = smoke_root / "application"
        app_root.mkdir()
        shutil.copy2(old_executable, app_root / "OAS-K.exe")

        layout = resolve_storage_layout(smoke_root / "DataRoot")
        SchemaManager().initialize_database(
            layout.database_path, PREVIOUS_VERSION, create_parent=True
        )
        core_storage = SimpleNamespace(
            resolve_status=lambda: SimpleNamespace(
                data_root=layout.data_root,
                database_path=layout.database_path,
                database_valid=True,
            )
        )
        analytics = AttendanceOTStorageService(core_storage)
        analytics_status = analytics.initialize()
        analytics_database = analytics_status.database_path
        assert analytics_database is not None

        with SQLiteConnectionFactory().connect(analytics_database) as connection:
            timestamp = "2026-10-02T00:00:00"
            cursor = connection.execute(
                """
                INSERT INTO source_registry (
                    source_type, source_path, filename, size_bytes,
                    modified_time_ns, row_count, status, imported_at,
                    fingerprint, error_detail, last_seen_at, created_at,
                    updated_at
                ) VALUES (
                    'ATTENDANCE_OT', 'C:/production/attendance.xlsx',
                    'attendance.xlsx', 4096, 123456789, 1, 'UNCHANGED', ?,
                    NULL, NULL, ?, ?, ?
                )
                """,
                (timestamp, timestamp, timestamp, timestamp),
            )
            source_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO attendance_records (
                    source_id, source_file, source_sheet, source_row, emplid,
                    date_in, time_in, date_out, time_out, overtime_hour,
                    overtime_minute, ot_amount, meal_ot_amount, location_descr,
                    name, paylink, job_title
                ) VALUES (?, 'C:/production/attendance.xlsx', 'Data', 2,
                          'PROD-001', '2026-10-01', '08:00:00', '2026-10-01',
                          '17:00:00', 1, 30, 150000, 25000, 'HEAD OFFICE',
                          'Production Employee', 'PG-PROD', 'Analyst')
                """,
                (source_id,),
            )
            connection.commit()

        baseline = _database_dump(analytics_database)
        backups_before = {
            path.name for path in analytics_database.parent.glob("*.bak")
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
        assert health.database_schema_version == CORE_SCHEMA

        current = analytics.initialize()
        assert current.database_valid
        assert current.schema_version == TARGET_ANALYTICS_SCHEMA
        assert _database_dump(analytics_database) == baseline
        assert {
            path.name for path in analytics_database.parent.glob("*.bak")
        } == backups_before
        with SQLiteConnectionFactory().connect(
            analytics_database, read_only=True
        ) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
            row = connection.execute(
                """
                SELECT emplid, name, paylink, job_title, ot_amount,
                       meal_ot_amount
                FROM attendance_records
                """
            ).fetchone()
            assert tuple(row) == (
                "PROD-001",
                "Production Employee",
                "PG-PROD",
                "Analyst",
                150000.0,
                25000.0,
            )
        gc.collect()

    return {
        "production_attendance_ot_schema": PRODUCTION_ANALYTICS_SCHEMA,
        "attendance_ot_schema_to": TARGET_ANALYTICS_SCHEMA,
        "attendance_ot_migration_path": "9->9 (no migration)",
        "attendance_ot_backup_required": False,
        "attendance_ot_data_preserved": True,
        "frozen_python_calamine_verified": True,
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
    analytics_report = _verify_schema9_preserved(package, old_executable)
    report_path = release / "verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(analytics_report)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
