"""Repository for normalized job history and external file references."""

from __future__ import annotations

import sqlite3

from shared.database.constants import UNIFIED_JOB_STATUSES
from shared.database.exceptions import RepositoryError
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.time_utils import current_timestamp, validate_date_pair

TERMINAL_JOB_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_WARNING",
    "FAILED",
    "CANCELLED",
    "NEED_REVIEW",
    "SKIPPED",
    "UPLOADED",
}


class JobRepository:
    """Persist standard statuses without importing or running an engine."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_job(self, record: JobHistoryRecord) -> int:
        """Insert a job and its initial status event atomically."""

        self._validate_status(record.unified_status)
        validate_date_pair(
            record.period_start_used,
            record.period_end_used,
        )
        try:
            cursor = self.connection.execute(
                """
                INSERT INTO job_history (
                    job_id,
                    module_code,
                    feature_code,
                    workflow,
                    legacy_status,
                    unified_status,
                    started_at,
                    finished_at,
                    duration_seconds,
                    output_path_used,
                    period_start_used,
                    period_end_used,
                    used_global_output,
                    used_global_period,
                    source_summary,
                    success_count,
                    warning_count,
                    failed_count,
                    skipped_count,
                    summary_json_path,
                    process_log_path,
                    error_message,
                    configuration_snapshot_hash,
                    created_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    record.job_id,
                    record.module_code,
                    record.feature_code,
                    record.workflow,
                    record.legacy_status,
                    record.unified_status,
                    record.started_at,
                    record.finished_at,
                    record.duration_seconds,
                    record.output_path_used,
                    record.period_start_used,
                    record.period_end_used,
                    int(record.used_global_output),
                    int(record.used_global_period),
                    record.source_summary,
                    record.success_count,
                    record.warning_count,
                    record.failed_count,
                    record.skipped_count,
                    record.summary_json_path,
                    record.process_log_path,
                    record.error_message,
                    record.configuration_snapshot_hash,
                    record.created_at,
                ),
            )
            job_pk = int(cursor.lastrowid)
            self._insert_status_event(
                job_pk=job_pk,
                unified_status=record.unified_status,
                legacy_status=record.legacy_status,
                occurred_at=record.started_at or record.created_at,
                phase="CREATED",
                message=None,
            )
            return job_pk
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to create job {record.module_code}/{record.job_id}: {exc}"
            ) from exc

    def update_job_status(
        self,
        *,
        module_code: str,
        job_id: str,
        unified_status: str,
        legacy_status: str | None = None,
        occurred_at: str | None = None,
        phase: str | None = None,
        message: str | None = None,
    ) -> None:
        """Update the current status and append a status event."""

        self._validate_status(unified_status)
        timestamp = occurred_at or current_timestamp()
        try:
            row = self.connection.execute(
                """
                SELECT job_pk
                FROM job_history
                WHERE module_code = ? AND job_id = ?
                """,
                (module_code, job_id),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"Job not found: {module_code}/{job_id}")
            job_pk = int(row["job_pk"])
            self.connection.execute(
                """
                UPDATE job_history
                SET unified_status = ?, legacy_status = ?
                WHERE job_pk = ?
                """,
                (unified_status, legacy_status, job_pk),
            )
            self._insert_status_event(
                job_pk=job_pk,
                unified_status=unified_status,
                legacy_status=legacy_status,
                occurred_at=timestamp,
                phase=phase,
                message=message,
            )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to update job status for {module_code}/{job_id}: {exc}"
            ) from exc

    def finish_job(
        self,
        *,
        module_code: str,
        job_id: str,
        unified_status: str,
        finished_at: str | None = None,
        duration_seconds: float | None = None,
        success_count: int = 0,
        warning_count: int = 0,
        failed_count: int = 0,
        skipped_count: int = 0,
        error_message: str | None = None,
        legacy_status: str | None = None,
    ) -> None:
        """Finish a job and append its terminal event."""

        self._validate_status(unified_status)
        if unified_status not in TERMINAL_JOB_STATUSES:
            raise ValueError(
                f"finish_job requires a terminal status, got {unified_status}."
            )
        if duration_seconds is not None and duration_seconds < 0:
            raise ValueError("duration_seconds must not be negative.")
        if (
            min(
                success_count,
                warning_count,
                failed_count,
                skipped_count,
            )
            < 0
        ):
            raise ValueError("Job result counts must not be negative.")

        timestamp = finished_at or current_timestamp()
        try:
            row = self.connection.execute(
                """
                SELECT job_pk
                FROM job_history
                WHERE module_code = ? AND job_id = ?
                """,
                (module_code, job_id),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"Job not found: {module_code}/{job_id}")
            job_pk = int(row["job_pk"])
            self.connection.execute(
                """
                UPDATE job_history
                SET
                    unified_status = ?,
                    legacy_status = ?,
                    finished_at = ?,
                    duration_seconds = ?,
                    success_count = ?,
                    warning_count = ?,
                    failed_count = ?,
                    skipped_count = ?,
                    error_message = ?
                WHERE job_pk = ?
                """,
                (
                    unified_status,
                    legacy_status,
                    timestamp,
                    duration_seconds,
                    success_count,
                    warning_count,
                    failed_count,
                    skipped_count,
                    error_message,
                    job_pk,
                ),
            )
            self._insert_status_event(
                job_pk=job_pk,
                unified_status=unified_status,
                legacy_status=legacy_status,
                occurred_at=timestamp,
                phase="FINISHED",
                message=error_message,
            )
        except RepositoryError:
            raise
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to finish job {module_code}/{job_id}: {exc}"
            ) from exc

    def add_job_file(self, record: JobFileRecord) -> int:
        """Add an external artifact reference for a job."""

        try:
            cursor = self.connection.execute(
                """
                INSERT INTO job_files (
                    job_pk,
                    file_role,
                    file_path,
                    file_size,
                    file_hash,
                    exists_at_last_check,
                    recorded_at,
                    last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_pk,
                    record.file_role,
                    record.file_path,
                    record.file_size,
                    record.file_hash,
                    int(record.exists_at_last_check),
                    record.recorded_at,
                    record.last_checked_at,
                ),
            )
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to add job file reference: {exc}") from exc

    def update_job_artifacts(
        self,
        job_pk: int,
        *,
        summary_json_path: str | None,
        process_log_path: str | None,
        source_summary: str | None = None,
    ) -> None:
        """Attach UI-normalized artifact references to an existing job."""

        try:
            self.connection.execute(
                """
                UPDATE job_history
                SET summary_json_path = ?, process_log_path = ?,
                    source_summary = COALESCE(?, source_summary)
                WHERE job_pk = ?
                """,
                (summary_json_path, process_log_path, source_summary, job_pk),
            )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to update job artifacts: {exc}") from exc

    def get_job_by_id(
        self,
        *,
        module_code: str,
        job_id: str,
    ) -> JobHistoryRecord | None:
        """Return a job by its module-scoped public ID."""

        try:
            row = self.connection.execute(
                self._select_sql() + " WHERE module_code = ? AND job_id = ?",
                (module_code, job_id),
            ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to read job: {exc}") from exc
        return self._to_job(row) if row is not None else None

    def list_recent_jobs(
        self,
        limit: int = 50,
        *,
        module_code: str | None = None,
    ) -> list[JobHistoryRecord]:
        """Return newest jobs with a bounded parameterized limit."""

        if limit <= 0:
            raise ValueError("limit must be greater than zero.")
        try:
            if module_code is None:
                rows = self.connection.execute(
                    self._select_sql()
                    + " ORDER BY COALESCE(started_at, created_at) DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    self._select_sql()
                    + """
                      WHERE module_code = ?
                      ORDER BY COALESCE(started_at, created_at) DESC
                      LIMIT ?
                    """,
                    (module_code, limit),
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to list recent jobs: {exc}") from exc
        return [self._to_job(row) for row in rows]

    def search_jobs(
        self,
        *,
        limit: int,
        offset: int = 0,
        module_code: str | None = None,
        unified_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search_text: str | None = None,
    ) -> list[JobHistoryRecord]:
        """Return one filtered page without loading all history."""

        where, parameters = self._search_where(
            module_code=module_code,
            unified_status=unified_status,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
        )
        if limit <= 0 or offset < 0:
            raise ValueError("limit must be positive and offset non-negative.")
        try:
            rows = self.connection.execute(
                self._select_sql()
                + where
                + " ORDER BY COALESCE(started_at, created_at) DESC LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to search jobs: {exc}") from exc
        return [self._to_job(row) for row in rows]

    def count_search_results(
        self,
        *,
        module_code: str | None = None,
        unified_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        search_text: str | None = None,
    ) -> int:
        """Count the same filtered result set used by ``search_jobs``."""

        where, parameters = self._search_where(
            module_code=module_code,
            unified_status=unified_status,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
        )
        try:
            row = self.connection.execute(
                "SELECT COUNT(*) FROM job_history" + where,
                parameters,
            ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to count jobs: {exc}") from exc
        return int(row[0])

    def count_jobs_by_module_status(self) -> list[sqlite3.Row]:
        """Return compact dashboard aggregates by module and status."""

        try:
            return self.connection.execute(
                """
                SELECT module_code, unified_status, COUNT(*) AS total
                FROM job_history
                GROUP BY module_code, unified_status
                ORDER BY module_code, unified_status
                """
            ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to aggregate jobs: {exc}") from exc

    def get_job_files(self, job_pk: int) -> list[sqlite3.Row]:
        try:
            return self.connection.execute(
                """
                SELECT file_role, file_path, file_size, exists_at_last_check,
                       recorded_at, last_checked_at
                FROM job_files WHERE job_pk = ? ORDER BY recorded_at, job_file_id
                """,
                (job_pk,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to read job files: {exc}") from exc

    def get_status_events(self, job_pk: int) -> list[sqlite3.Row]:
        try:
            return self.connection.execute(
                """
                SELECT occurred_at, unified_status, legacy_status, phase, message
                FROM job_status_events WHERE job_pk = ?
                ORDER BY occurred_at, status_event_id
                """,
                (job_pk,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Unable to read status events: {exc}") from exc

    @staticmethod
    def _search_where(
        *,
        module_code: str | None,
        unified_status: str | None,
        date_from: str | None,
        date_to: str | None,
        search_text: str | None,
    ) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = []
        parameters: list[object] = []
        if module_code:
            clauses.append("module_code = ?")
            parameters.append(module_code)
        if unified_status:
            clauses.append("unified_status = ?")
            parameters.append(unified_status)
        timestamp = "date(COALESCE(started_at, created_at))"
        if date_from:
            clauses.append(f"{timestamp} >= date(?)")
            parameters.append(date_from)
        if date_to:
            clauses.append(f"{timestamp} <= date(?)")
            parameters.append(date_to)
        if search_text:
            pattern = f"%{search_text.strip()}%"
            clauses.append(
                "(job_id LIKE ? OR module_code LIKE ? OR workflow LIKE ? "
                "OR output_path_used LIKE ? OR error_message LIKE ?)"
            )
            parameters.extend([pattern] * 5)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return where, tuple(parameters)

    def _insert_status_event(
        self,
        *,
        job_pk: int,
        unified_status: str,
        legacy_status: str | None,
        occurred_at: str,
        phase: str | None,
        message: str | None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO job_status_events (
                job_pk,
                occurred_at,
                legacy_status,
                unified_status,
                phase,
                message
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_pk,
                occurred_at,
                legacy_status,
                unified_status,
                phase,
                message,
            ),
        )

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in UNIFIED_JOB_STATUSES:
            raise ValueError(f"Unsupported Unified job status: {status}")

    @staticmethod
    def _select_sql() -> str:
        return """
            SELECT
                job_pk,
                job_id,
                module_code,
                feature_code,
                workflow,
                legacy_status,
                unified_status,
                started_at,
                finished_at,
                duration_seconds,
                output_path_used,
                period_start_used,
                period_end_used,
                used_global_output,
                used_global_period,
                source_summary,
                success_count,
                warning_count,
                failed_count,
                skipped_count,
                summary_json_path,
                process_log_path,
                error_message,
                configuration_snapshot_hash,
                created_at
            FROM job_history
        """

    @staticmethod
    def _to_job(row: sqlite3.Row) -> JobHistoryRecord:
        values = dict(row)
        values["used_global_output"] = bool(values["used_global_output"])
        values["used_global_period"] = bool(values["used_global_period"])
        return JobHistoryRecord(**values)
