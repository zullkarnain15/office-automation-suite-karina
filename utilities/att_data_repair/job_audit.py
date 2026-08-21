"""SQLite job-history adapter for Att Data Repair."""

from __future__ import annotations

from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import JobRepository
from utilities.att_data_repair.artifacts import (
    AttDataRepairJobRequest,
    AttDataRepairJobResult,
)
from utilities.att_data_repair.process_logger import AttDataRepairProcessLogger
from utilities.att_data_repair.statuses import JobStatus

MODULE_CODE = "UTILITIES"
FEATURE_CODE = "Att Data Repair"


class AttDataRepairJobAudit:
    """Persist Att Data Repair job history without coupling the engine to DB."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def record(
        self,
        database_path: str | Path,
        request: AttDataRepairJobRequest,
        result: AttDataRepairJobResult,
    ) -> int:
        """Record job_history, job_files, and job_status_events in one transaction."""

        started = result.started_at.isoformat(timespec="seconds")
        completed = result.completed_at.isoformat(timespec="seconds")
        unified = _unified_status(result.status)
        duration = max(0.0, (result.completed_at - result.started_at).total_seconds())
        with self.connection_factory.connect(database_path) as connection:
            repository = JobRepository(connection)
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=result.job_id,
                    module_code=MODULE_CODE,
                    feature_code=FEATURE_CODE,
                    workflow=None,
                    legacy_status=result.status,
                    unified_status="RUNNING",
                    started_at=started,
                    finished_at=None,
                    duration_seconds=None,
                    output_path_used=str(result.paths.job_folder),
                    period_start_used=request.analysis_request.period_start.isoformat(),
                    period_end_used=request.analysis_request.period_end.isoformat(),
                    used_global_output=False,
                    used_global_period=False,
                    source_summary=str(request.analysis_request.source_report),
                    success_count=0,
                    warning_count=0,
                    failed_count=0,
                    skipped_count=0,
                    summary_json_path=None,
                    process_log_path=None,
                    error_message=None,
                    configuration_snapshot_hash=None,
                    created_at=started,
                )
            )
            for phase, message in _phase_events(result):
                repository.update_job_status(
                    module_code=MODULE_CODE,
                    job_id=result.job_id,
                    unified_status="RUNNING",
                    legacy_status=result.status,
                    occurred_at=started,
                    phase=phase,
                    message=message,
                )
            repository.update_job_artifacts(
                job_pk,
                summary_json_path=str(result.paths.summary_json),
                process_log_path=str(result.paths.process_log),
                source_summary=str(request.analysis_request.source_report),
            )
            for role, path in _job_files(result):
                if not path.exists():
                    continue
                repository.add_job_file(
                    JobFileRecord(
                        job_pk=job_pk,
                        file_role=role,
                        file_path=str(path),
                        file_size=path.stat().st_size if path.is_file() else None,
                        exists_at_last_check=True,
                        recorded_at=completed,
                        last_checked_at=completed,
                    )
                )
            repository.finish_job(
                module_code=MODULE_CODE,
                job_id=result.job_id,
                unified_status=unified,
                legacy_status=result.status,
                finished_at=completed,
                duration_seconds=duration,
                success_count=len(result.analysis_result.final_records),
                warning_count=len(result.analysis_result.anomalies),
                failed_count=len(result.analysis_result.anomalies)
                if result.status in {JobStatus.NO_VALID_RECORDS, JobStatus.FAILED}
                else 0,
                error_message=result.error_message,
            )
            repository.update_job_status(
                module_code=MODULE_CODE,
                job_id=result.job_id,
                unified_status=unified,
                legacy_status=result.status,
                occurred_at=completed,
                phase="COMPLETED" if unified != "FAILED" else "FAILED",
                message=result.error_message,
            )
        return job_pk

    def safe_record(
        self,
        database_path: str | Path,
        request: AttDataRepairJobRequest,
        result: AttDataRepairJobResult,
    ) -> bool:
        """Record history and log an error without deleting successful outputs."""

        try:
            self.record(database_path, request, result)
        except Exception as exc:
            logger = AttDataRepairProcessLogger(result.paths.process_log)
            logger.error(f"History write failed: {type(exc).__name__}: {exc}")
            return False
        return True


def _unified_status(status: str) -> str:
    if status == JobStatus.SUCCESS:
        return "COMPLETED"
    if status in {JobStatus.PARTIAL_SUCCESS, JobStatus.NO_VALID_RECORDS}:
        return "COMPLETED_WITH_WARNING"
    return "FAILED"


def _phase_events(
    result: AttDataRepairJobResult,
) -> tuple[tuple[str, str], ...]:
    events: list[tuple[str, str]] = [
        ("STARTED", "Att Data Repair job started."),
        ("ANALYZED", "Source report analyzed."),
    ]
    if result.txt_artifacts:
        events.append(("TXT_GENERATED", "TXT artifacts generated."))
    if result.report_artifact is not None:
        events.append(("REPORT_GENERATED", "Excel report generated."))
    if result.status == JobStatus.FAILED:
        events.append(("FAILED", result.error_message or "Job failed."))
    else:
        events.append(("COMPLETED", "Job completed."))
    return tuple(events)


def _job_files(
    result: AttDataRepairJobResult,
) -> tuple[tuple[str, Path], ...]:
    files: list[tuple[str, Path]] = []
    for artifact in result.txt_artifacts:
        files.append(("HRIS_TXT", artifact.file_path))
    if result.report_artifact is not None:
        files.append(("EXCEL_REPORT", result.report_artifact.file_path))
    files.extend(
        (
            ("PROCESS_LOG", result.paths.process_log),
            ("SUMMARY_JSON", result.paths.summary_json),
        )
    )
    return tuple(files)
