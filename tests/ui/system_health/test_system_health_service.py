from __future__ import annotations

from pathlib import Path

from shared.database import SQLiteConnectionFactory, SchemaManager
from ui.services.protocols import StorageStatusView
from ui.services.system_health_service import (
    HealthCheckResult,
    HealthStatus,
    SystemHealthService,
)


class Storage:
    def __init__(self, root: Path, database: Path, valid: bool):
        self.root, self.database, self.valid = root, database, valid

    def resolve_status(self):
        return StorageStatusView(
            "READY" if self.valid else "RECOVERY_REQUIRED",
            self.root,
            self.database,
            self.database.exists(),
            self.valid,
            1 if self.valid else None,
            "test",
            "Tersedia",
            self.root / "recorder_profiles" / "hris",
            self.root / "backup",
            self.root / "output",
            self.root / "logs",
            self.root / "diagnostics",
        )


def test_page_service_does_not_run_until_explicit_call(tmp_path: Path) -> None:
    service = SystemHealthService(Storage(tmp_path, tmp_path / "missing.db", False))
    assert service.get_summary().overall == HealthStatus.NOT_CHECKED
    assert service.get_last_result() == ()


def test_health_results_are_typed_and_zero_write(tmp_path: Path) -> None:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "ui3-test")
    before = database.stat().st_mtime_ns
    service = SystemHealthService(Storage(tmp_path, database, True))
    results = service.run_all_checks()
    assert all(isinstance(item, HealthCheckResult) for item in results)
    assert {item.code for item in results} >= {
        "database",
        "data_root",
        "registry",
        "profiles",
        "attendance",
        "outlook",
        "hris",
        "utilities",
        "write_access",
        "recovery",
    }
    assert database.stat().st_mtime_ns == before
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM system_health_history").fetchone()[
                0
            ]
            == 0
        )


def test_missing_configuration_is_not_configured(tmp_path: Path) -> None:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "ui3-test")
    results = SystemHealthService(Storage(tmp_path, database, True)).run_all_checks()
    readiness = {item.code: item.status for item in results}
    assert readiness["attendance"] == HealthStatus.NOT_CONFIGURED
    assert readiness["outlook"] == HealthStatus.NOT_CONFIGURED
    assert readiness["hris"] == HealthStatus.NOT_CONFIGURED


def test_corrupt_and_missing_database_do_not_crash(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_text("not sqlite", encoding="utf-8")
    corrupt_results = SystemHealthService(
        Storage(tmp_path, corrupt, False)
    ).run_all_checks()
    assert (
        next(item for item in corrupt_results if item.code == "database").status
        == HealthStatus.ERROR
    )
    missing = tmp_path / "missing.db"
    missing_results = SystemHealthService(
        Storage(tmp_path, missing, False)
    ).run_all_checks()
    assert (
        next(item for item in missing_results if item.code == "database").status
        == HealthStatus.UNAVAILABLE
    )
