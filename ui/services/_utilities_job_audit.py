"""Shared UI7 job-history lifecycle helpers."""

from __future__ import annotations

from datetime import datetime

from shared.database import SQLiteConnectionFactory
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import JobRepository
from shared.database.time_utils import current_timestamp
from ui.utilities_models import UtilitiesJobPhase

TERMINAL = {"COMPLETED", "COMPLETED_WITH_WARNING", "FAILED", "CANCELLED"}


class UtilitiesJobAudit:
    def __init__(self, factory: SQLiteConnectionFactory | None = None) -> None:
        self.factory = factory or SQLiteConnectionFactory()

    def start(self, database, resolved, feature: str, source: str) -> int:
        now = current_timestamp()
        with self.factory.connect(database) as connection:
            repository = JobRepository(connection)
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=resolved.job_id,
                    module_code="UTILITIES",
                    feature_code=feature,
                    workflow=resolved.workflow,
                    unified_status="PENDING",
                    output_path_used=str(resolved.output_root),
                    period_start_used=getattr(resolved, "period_start", None),
                    period_end_used=getattr(resolved, "period_end", None),
                    used_global_output=resolved.used_global_output,
                    used_global_period=getattr(resolved, "used_global_period", False),
                    source_summary=source,
                    created_at=now,
                    started_at=now,
                )
            )
            repository.update_job_status(
                module_code="UTILITIES",
                job_id=resolved.job_id,
                unified_status="PENDING",
                phase=UtilitiesJobPhase.JOB_CREATED,
                message=f"{feature} job created.",
            )
        return job_pk

    def event(
        self, database, job_id: str, phase: UtilitiesJobPhase, message: str
    ) -> None:
        with self.factory.connect(database) as connection:
            JobRepository(connection).update_job_status(
                module_code="UTILITIES",
                job_id=job_id,
                unified_status="RUNNING",
                phase=phase,
                message=message,
            )

    def finish(self, database, job_pk: int, result) -> None:
        status = (
            "CANCELLED"
            if result.cancelled
            else "COMPLETED_WITH_WARNING"
            if result.success and result.warning_count
            else "COMPLETED"
            if result.success
            else "FAILED"
        )
        duration = max(
            0.0,
            (
                datetime.fromisoformat(result.ended_at)
                - datetime.fromisoformat(result.started_at)
            ).total_seconds(),
        )
        summary = next(
            (item.path for item in result.outputs if item.role == "SUMMARY_JSON"), None
        )
        process = next(
            (item.path for item in result.outputs if item.role == "PROCESS_LOG"), None
        )
        with self.factory.connect(database) as connection:
            repository = JobRepository(connection)
            repository.finish_job(
                module_code="UTILITIES",
                job_id=result.job_id,
                unified_status=status,
                finished_at=result.ended_at,
                duration_seconds=duration,
                success_count=getattr(
                    result, "total_records", getattr(result, "files_accepted", 0)
                ),
                warning_count=result.warning_count,
                failed_count=getattr(
                    result, "invalid_count", getattr(result, "files_rejected", 0)
                ),
                error_message=result.error_summary,
                legacy_status="SUCCESS" if result.success else status,
            )
            repository.update_job_artifacts(
                job_pk,
                summary_json_path=str(summary) if summary else None,
                process_log_path=str(process) if process else None,
            )
            for output in result.outputs:
                if not output.path.exists():
                    continue
                repository.add_job_file(
                    JobFileRecord(
                        job_pk=job_pk,
                        file_role=output.role,
                        file_path=str(output.path),
                        file_size=output.path.stat().st_size
                        if output.path.is_file()
                        else None,
                        exists_at_last_check=True,
                        recorded_at=result.ended_at,
                        last_checked_at=result.ended_at,
                    )
                )
            repository.update_job_status(
                module_code="UTILITIES",
                job_id=result.job_id,
                unified_status=status,
                legacy_status="SUCCESS" if result.success else status,
                occurred_at=result.ended_at,
                phase=(
                    UtilitiesJobPhase.JOB_CANCELLED
                    if result.cancelled
                    else UtilitiesJobPhase.JOB_COMPLETED
                    if result.success
                    else UtilitiesJobPhase.JOB_FAILED
                ),
                message=result.error_summary,
            )

    def cancel(self, database, job_id: str, token) -> None:
        token.request()
        with self.factory.connect(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT unified_status FROM job_history "
                "WHERE module_code='UTILITIES' AND job_id=?",
                (job_id,),
            ).fetchone()
            if row is None or row["unified_status"] in TERMINAL:
                return
            JobRepository(connection).update_job_status(
                module_code="UTILITIES",
                job_id=job_id,
                unified_status="PAUSED",
                legacy_status="CANCEL_REQUESTED",
                phase=UtilitiesJobPhase.CANCEL_REQUESTED,
                message="Cancellation requested; waiting for safe checkpoint.",
            )
