"""Read-only dashboard aggregation over storage and schema-v1 history."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.repositories import BackupHistoryRepository, JobRepository
from ui.services.protocols import StorageStatusView

MODULES = ("ATTENDANCE", "OUTLOOK_REVISI", "HRIS", "UTILITIES")
SUCCESS_STATUSES = {"COMPLETED", "COMPLETED_WITH_WARNING", "UPLOADED"}


@dataclass(frozen=True, slots=True)
class ModuleSummary:
    module: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    last_run: str | None = None
    last_status: str = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class ActivityItem:
    job_pk: int
    occurred_at: str
    module: str
    workflow: str | None
    status: str
    output_path: Path | None


@dataclass(frozen=True, slots=True)
class BackupSummary:
    available: bool
    status: str = "Belum ada backup"
    backup_path: Path | None = None
    occurred_at: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    available: bool
    database_status: str
    data_root_status: str
    last_backup: BackupSummary
    system_health_status: str
    modules: tuple[ModuleSummary, ...]
    recent_activity: tuple[ActivityItem, ...]
    message: str = ""


class DashboardService:
    def __init__(self, storage_service, *, database_path: Path | None = None) -> None:
        self.storage_service = storage_service
        self.database_path = database_path
        self.connection_factory = SQLiteConnectionFactory()

    def get_dashboard_summary(self) -> DashboardSummary:
        storage = self.get_storage_summary()
        database = self.database_path or storage.database_path
        if not database or not database.is_file() or not storage.database_valid:
            return DashboardSummary(
                False,
                "Unavailable" if not storage.database_exists else "Invalid",
                storage.resolution_status,
                BackupSummary(False),
                "NOT_CHECKED",
                tuple(ModuleSummary(module) for module in MODULES),
                (),
                "Database belum tersedia atau tidak valid.",
            )
        try:
            return DashboardSummary(
                True,
                "Healthy",
                storage.resolution_status,
                self.get_backup_summary(database),
                self._latest_health_status(database),
                self.get_module_summaries(database),
                self.get_recent_activity(10, database),
            )
        except Exception as exc:
            return DashboardSummary(
                False,
                "Error",
                storage.resolution_status,
                BackupSummary(False),
                "UNAVAILABLE",
                tuple(ModuleSummary(module) for module in MODULES),
                (),
                str(exc),
            )

    def get_storage_summary(self) -> StorageStatusView:
        return self.storage_service.resolve_status()

    def get_module_summaries(
        self, database_path: Path | None = None
    ) -> tuple[ModuleSummary, ...]:
        database = database_path or self.database_path
        if not database or not database.is_file():
            return tuple(ModuleSummary(module) for module in MODULES)
        with self.connection_factory.connect(database, read_only=True) as connection:
            repository = JobRepository(connection)
            counts: dict[str, dict[str, int]] = {}
            for row in repository.count_jobs_by_module_status():
                counts.setdefault(str(row["module_code"]), {})[
                    str(row["unified_status"])
                ] = int(row["total"])
            result = []
            for module in MODULES:
                statuses = counts.get(module, {})
                recent = repository.list_recent_jobs(1, module_code=module)
                latest = recent[0] if recent else None
                result.append(
                    ModuleSummary(
                        module,
                        sum(statuses.values()),
                        sum(statuses.get(item, 0) for item in SUCCESS_STATUSES),
                        statuses.get("FAILED", 0),
                        (latest.started_at or latest.created_at) if latest else None,
                        latest.unified_status if latest else "NOT_AVAILABLE",
                    )
                )
            return tuple(result)

    def get_recent_activity(
        self, limit: int = 10, database_path: Path | None = None
    ) -> tuple[ActivityItem, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        database = database_path or self.database_path
        if not database or not database.is_file():
            return ()
        with self.connection_factory.connect(database, read_only=True) as connection:
            jobs = JobRepository(connection).list_recent_jobs(limit)
        return tuple(
            ActivityItem(
                int(job.job_pk or 0),
                job.started_at or job.created_at,
                job.module_code,
                job.workflow,
                job.unified_status,
                Path(job.output_path_used) if job.output_path_used else None,
            )
            for job in jobs
        )

    def get_backup_summary(self, database_path: Path | None = None) -> BackupSummary:
        database = database_path or self.database_path
        if not database or not database.is_file():
            return BackupSummary(False)
        with self.connection_factory.connect(database, read_only=True) as connection:
            record = BackupHistoryRepository(connection).get_latest_backup()
        if record is None:
            return BackupSummary(False)
        return BackupSummary(
            True,
            record.status,
            Path(record.backup_path) if record.backup_path else None,
            record.finished_at or record.started_at,
        )

    def _latest_health_status(self, database_path: Path) -> str:
        with self.connection_factory.connect(
            database_path, read_only=True
        ) as connection:
            row = connection.execute(
                "SELECT status FROM system_health_history "
                "ORDER BY checked_at DESC, health_check_id DESC LIMIT 1"
            ).fetchone()
        return str(row[0]) if row else "NOT_CHECKED"
