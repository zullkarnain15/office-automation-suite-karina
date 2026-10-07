"""Isolated release-gate verification for OAS-K 1.0.14."""

from __future__ import annotations

import gc
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE_VERIFIER = Path(__file__).with_name("verify_release_1_0_11.py")
VERSION = "1.0.14"
PREVIOUS_VERSION = "1.0.13"
CORE_SCHEMA = 4
ANALYTICS_SCHEMA = 5


def _database_dump(path: Path) -> tuple[str, ...]:
    from shared.database.connection_factory import SQLiteConnectionFactory

    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        return tuple(connection.iterdump())


def _verify_analytics_schema() -> None:
    from shared.attendance_ot.schema import ANALYTICS_SCHEMA_VERSION
    from shared.attendance_ot.storage import AttendanceOTStorageService

    assert ANALYTICS_SCHEMA_VERSION == ANALYTICS_SCHEMA
    temp_parent = ROOT / ".codex_tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="analytics_schema5_release_", dir=temp_parent
    ) as temp_name:
        data_root = Path(temp_name) / "DataRoot"
        core_storage = SimpleNamespace(
            resolve_status=lambda: SimpleNamespace(
                data_root=data_root,
                database_valid=True,
            )
        )
        service = AttendanceOTStorageService(core_storage)
        initialized = service.initialize()
        assert initialized.database_valid
        assert initialized.schema_version == ANALYTICS_SCHEMA
        database = initialized.database_path
        assert database is not None

        with service.connection_factory.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO analytics_monthly_employee (
                    year_month, emplid, employee_name, classification, branch,
                    department, division, pay_group, total_records, late_count,
                    total_ot_minutes, ot_amount, meal_ot_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-09",
                    "RELEASE-001",
                    "Production Fixture",
                    "HO",
                    "",
                    "Finance",
                    "Corporate",
                    "HO",
                    20,
                    2,
                    60.0,
                    100000.0,
                    25000.0,
                ),
            )
            connection.commit()
        baseline = _database_dump(database)

        accepted = service.initialize()
        assert accepted.database_valid
        assert accepted.schema_version == ANALYTICS_SCHEMA
        assert _database_dump(database) == baseline
        gc.collect()


def main() -> None:
    _verify_analytics_schema()
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

    report_path = ROOT / "dist" / "release" / f"v{VERSION}" / "verification.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "production_core_schema": CORE_SCHEMA,
            "attendance_ot_schema": ANALYTICS_SCHEMA,
            "attendance_ot_schema_accepted": True,
            "attendance_ot_data_preserved": True,
        }
    )
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
