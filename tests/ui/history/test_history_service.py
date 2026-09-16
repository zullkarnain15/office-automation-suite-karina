from __future__ import annotations

from pathlib import Path

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import JobRepository
from ui.services.history_service import HistoryFilters, HistoryService


class Storage:
    def resolve_status(self):
        raise AssertionError("explicit test database should be used")


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(path, "ui3-test")
    with SQLiteConnectionFactory().connect(path) as connection:
        repository = JobRepository(connection)
        for number in range(1, 31):
            module = "HRIS" if number % 2 else "ATTENDANCE"
            status = "FAILED" if number % 3 == 0 else "COMPLETED"
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=f"JOB-{number:03}",
                    module_code=module,
                    workflow="HO",
                    unified_status=status,
                    output_path_used=f"D:/Output/{number}",
                    period_start_used="2026-07-01",
                    period_end_used="2026-07-31",
                    used_global_output=True,
                    used_global_period=True,
                    created_at=f"2026-07-{number:02}T10:00:00",
                    started_at=f"2026-07-{number:02}T10:00:00",
                    duration_seconds=float(number),
                )
            )
            if number == 1:
                repository.add_job_file(
                    JobFileRecord(
                        job_pk=job_pk,
                        file_role="REPORT",
                        file_path="D:/Output/report.json",
                        recorded_at="2026-07-01T10:01:00",
                    )
                )
    return path


def test_history_filters_module_status_and_date(tmp_path: Path) -> None:
    service = HistoryService(Storage(), database_path=_database(tmp_path))
    assert service.search(HistoryFilters(module="HRIS"), limit=50).total == 15
    assert service.search(HistoryFilters(status="FAILED"), limit=50).total == 10
    result = service.search(
        HistoryFilters(date_from="2026-07-10", date_to="2026-07-12"), limit=50
    )
    assert result.total == 3


def test_history_pagination_total_and_search(tmp_path: Path) -> None:
    service = HistoryService(Storage(), database_path=_database(tmp_path))
    first = service.search(limit=25, offset=0)
    second = service.search(limit=25, offset=25)
    assert first.total == 30 and len(first.items) == 25
    assert second.total == 30 and len(second.items) == 5
    assert service.search(HistoryFilters(search_text="JOB-001"), limit=25).total == 1


def test_history_detail_includes_files_and_events(tmp_path: Path) -> None:
    service = HistoryService(Storage(), database_path=_database(tmp_path))
    detail = service.get_job_detail("HRIS", "JOB-001")
    assert detail is not None
    assert detail.files[0]["file_role"] == "REPORT"
    assert detail.events[0]["unified_status"] == "COMPLETED"


def test_missing_database_is_empty_and_not_created(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"
    result = HistoryService(Storage(), database_path=database).search()
    assert not result.available and result.total == 0
    assert not database.exists()
