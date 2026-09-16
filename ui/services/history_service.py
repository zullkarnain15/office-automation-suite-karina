"""Paged, filtered, read-only job history facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.models import JobHistoryRecord
from shared.database.repositories import JobRepository


@dataclass(frozen=True, slots=True)
class HistoryFilters:
    module: str | None = None
    status: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    search_text: str | None = None


@dataclass(frozen=True, slots=True)
class HistoryPageResult:
    items: tuple[JobHistoryRecord, ...]
    total: int
    limit: int
    offset: int
    available: bool = True
    message: str = ""


@dataclass(frozen=True, slots=True)
class JobDetail:
    job: JobHistoryRecord
    files: tuple[dict[str, object], ...]
    events: tuple[dict[str, object], ...]


class HistoryService:
    def __init__(self, storage_service, *, database_path: Path | None = None) -> None:
        self.storage_service = storage_service
        self.database_path = database_path
        self.connection_factory = SQLiteConnectionFactory()

    def search(
        self,
        filters: HistoryFilters = HistoryFilters(),
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> HistoryPageResult:
        database = self._database()
        if database is None:
            return HistoryPageResult(
                (), 0, limit, offset, False, "Database unavailable"
            )
        with self.connection_factory.connect(database, read_only=True) as connection:
            repository = JobRepository(connection)
            arguments = {
                "module_code": filters.module,
                "unified_status": filters.status,
                "date_from": filters.date_from,
                "date_to": filters.date_to,
                "search_text": filters.search_text,
            }
            total = repository.count_search_results(**arguments)
            items = repository.search_jobs(limit=limit, offset=offset, **arguments)
        return HistoryPageResult(tuple(items), total, limit, offset)

    def get_job_detail(self, module_code: str, job_id: str) -> JobDetail | None:
        database = self._database()
        if database is None:
            return None
        with self.connection_factory.connect(database, read_only=True) as connection:
            repository = JobRepository(connection)
            job = repository.get_job_by_id(module_code=module_code, job_id=job_id)
            if job is None or job.job_pk is None:
                return None
            files = tuple(dict(row) for row in repository.get_job_files(job.job_pk))
            events = tuple(
                dict(row) for row in repository.get_status_events(job.job_pk)
            )
        return JobDetail(job, files, events)

    def _database(self) -> Path | None:
        if self.database_path is not None:
            return self.database_path if self.database_path.is_file() else None
        status = self.storage_service.resolve_status()
        if not status.database_valid or status.database_path is None:
            return None
        return status.database_path
