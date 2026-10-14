from __future__ import annotations

from pathlib import Path

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.models import BackupHistoryRecord, JobHistoryRecord
from shared.database.repositories import BackupHistoryRepository, JobRepository
from ui.services.dashboard_service import DashboardService
from ui.services.protocols import StorageStatusView


class Storage:
    def __init__(self, root: Path, database: Path, *, valid: bool = True):
        self.root = root
        self.database = database
        self.valid = valid

    def resolve_status(self):
        return StorageStatusView(
            "READY" if self.valid else "INITIAL_SETUP_REQUIRED",
            self.root,
            self.database,
            self.database.is_file(),
            self.valid and self.database.is_file(),
            1 if self.valid and self.database.is_file() else None,
            "test",
            "Tersedia",
            self.root / "recorder_profiles" / "hris",
            self.root / "backup",
            self.root / "output",
            self.root / "logs",
            self.root / "diagnostics",
        )


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "database" / "OAS-K.db"
    SchemaManager().initialize_database(path, "ui3-test", create_parent=True)
    return path


def _job(repository, number, module="ATTENDANCE", status="COMPLETED"):
    return repository.create_job(
        JobHistoryRecord(
            job_id=f"JOB-{number:03}",
            module_code=module,
            unified_status=status,
            output_path_used=f"D:/Output/{number}",
            used_global_output=True,
            used_global_period=True,
            created_at=f"2026-07-{number:02}T10:00:00",
            started_at=f"2026-07-{number:02}T10:00:00",
        )
    )


def test_dashboard_unavailable_does_not_create_database(tmp_path: Path) -> None:
    database = tmp_path / "missing" / "OAS-K.db"
    summary = DashboardService(
        Storage(tmp_path, database, valid=False)
    ).get_dashboard_summary()
    assert not summary.available
    assert not database.exists()
    assert not database.parent.exists()


def test_dashboard_module_summary_recent_limit_and_backup(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with SQLiteConnectionFactory().connect(database) as connection:
        jobs = JobRepository(connection)
        _job(jobs, 1)
        _job(jobs, 2, status="FAILED")
        _job(jobs, 3, module="HRIS", status="RUNNING")
        BackupHistoryRepository(connection).add_backup_history(
            BackupHistoryRecord(
                action_type="BACKUP",
                source_path=str(database),
                backup_path=str(tmp_path / "backup" / "one.db"),
                started_at="2026-07-20T10:00:00",
                finished_at="2026-07-20T10:01:00",
                status="SUCCESS",
            )
        )
    service = DashboardService(Storage(tmp_path, database))
    modules = {item.module: item for item in service.get_module_summaries(database)}
    assert modules["ATTENDANCE"].total == 2
    assert modules["ATTENDANCE"].succeeded == 1
    assert modules["ATTENDANCE"].failed == 1
    assert len(service.get_recent_activity(2, database)) == 2
    assert service.get_backup_summary(database).available


def test_dashboard_summary_is_read_only(tmp_path: Path) -> None:
    database = _database(tmp_path)
    before = database.stat().st_mtime_ns
    summary = DashboardService(Storage(tmp_path, database)).get_dashboard_summary()
    assert summary.available
    assert database.stat().st_mtime_ns == before
