"""Attendance UI4 orchestration, resolution, and audit lifecycle."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.exceptions import RepositoryError
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from shared.database.time_utils import current_timestamp
from ui.attendance_models import (
    AttendanceCancellationToken,
    AttendanceDefaults,
    AttendanceLogEvent,
    AttendanceProgressEvent,
    AttendanceResolvedRequest,
    AttendanceRunRequest,
    AttendanceRunResult,
)
from ui.services.module_configuration_service import ModuleConfigurationService

_TERMINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_WARNING",
    "FAILED",
    "CANCELLED",
    "SKIPPED",
    "UPLOADED",
}


class AttendanceService:
    def __init__(self, storage_service, adapter) -> None:
        self.storage_service = storage_service
        self.adapter = adapter
        self.factory = SQLiteConnectionFactory()
        self.module_configurations = ModuleConfigurationService(self.factory)

    def load_active_configuration(self):
        defaults = self.load_defaults()
        summaries = self.module_configurations.load_summaries(defaults.database_path)
        return next(item for item in summaries if item.module == "ATTENDANCE")

    def load_defaults(self) -> AttendanceDefaults:
        storage = self.storage_service.resolve_status()
        database = storage.database_path
        if not storage.database_valid or database is None:
            return AttendanceDefaults(
                False,
                database,
                warning=(
                    "Data Location belum disiapkan. Siapkan melalui Settings untuk "
                    "menjalankan Attendance dari Unified UI."
                ),
            )
        with self.factory.connect(database, read_only=True) as connection:
            global_value = GlobalSettingsRepository(connection).get_global_settings()
            module = connection.execute(
                "SELECT use_global_output, use_global_period "
                "FROM attendance_settings LIMIT 1"
            ).fetchone()
        return AttendanceDefaults(
            True,
            database,
            bool(module and module["use_global_output"]),
            bool(module and module["use_global_period"]),
            Path(global_value.output_root)
            if global_value and global_value.output_root
            else None,
            global_value.period_start if global_value else None,
            global_value.period_end if global_value else None,
        )

    def resolve_request(
        self, request: AttendanceRunRequest, *, require_database: bool
    ) -> AttendanceResolvedRequest:
        if request.workflow not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")
        if not request.generate_txt and not request.generate_report:
            raise ValueError("Minimal satu output harus dipilih.")
        if request.configuration_path is not None:
            if request.configuration_path.suffix.casefold() != ".xlsx":
                raise ValueError("Attendance Configuration harus berupa file .xlsx.")
            if not request.configuration_path.is_file():
                raise ValueError("Attendance Configuration tidak ditemukan.")
        defaults = self.load_defaults()
        if require_database and not defaults.database_available:
            raise RuntimeError(defaults.warning)
        if request.configuration_path is None and not defaults.database_available:
            raise RuntimeError(
                "Konfigurasi aktif SQLite belum tersedia. Gunakan fallback Excel "
                "atau siapkan database melalui Settings."
            )
        if request.use_global_period:
            start, end = defaults.global_period_start, defaults.global_period_end
            if not defaults.database_available or not start or not end:
                raise ValueError("Global period belum tersedia.")
        else:
            start, end = request.override_period_start, request.override_period_end
        self._validate_period(start, end)
        if request.use_global_output:
            output = defaults.global_output_root
            if not defaults.database_available or output is None:
                raise ValueError("Global output belum tersedia.")
        else:
            output = request.override_output_root
        if output is None or not str(output).strip():
            raise ValueError("Output Root wajib diisi.")
        output = output.expanduser()
        self._validate_output_parent(output)
        return AttendanceResolvedRequest(
            self._new_job_id(),
            defaults.database_path if defaults.database_available else None,
            request.configuration_path,
            request.workflow,
            output,
            str(start),
            str(end),
            request.use_global_output,
            request.use_global_period,
            request.generate_txt,
            request.generate_report,
        )

    def preflight(
        self,
        request: AttendanceRunRequest,
        *,
        require_database: bool,
    ):
        resolved = self.resolve_request(request, require_database=require_database)
        return resolved, self.adapter.validate_configuration(resolved)

    def validate(self, request: AttendanceRunRequest):
        return self.preflight(request, require_database=False)

    def run_job(
        self,
        resolved: AttendanceResolvedRequest,
        *,
        cancellation: AttendanceCancellationToken,
        progress: Callable[[AttendanceProgressEvent], None],
        log: Callable[[AttendanceLogEvent], None],
    ) -> AttendanceRunResult:
        if resolved.database_path is None:
            raise RuntimeError("Database audit Attendance tidak tersedia.")
        started = current_timestamp()
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=resolved.job_id,
                    module_code="ATTENDANCE",
                    workflow=resolved.workflow,
                    unified_status="PENDING",
                    output_path_used=str(resolved.output_root),
                    period_start_used=resolved.period_start,
                    period_end_used=resolved.period_end,
                    used_global_output=resolved.used_global_output,
                    used_global_period=resolved.used_global_period,
                    source_summary=(
                        str(resolved.configuration_path)
                        if resolved.configuration_path
                        else "OAS-K Database"
                    ),
                    created_at=started,
                    started_at=started,
                )
            )
            repository.update_job_status(
                module_code="ATTENDANCE",
                job_id=resolved.job_id,
                unified_status="RUNNING",
                phase="ENGINE",
                message="Attendance engine started.",
            )
        try:
            result = self.adapter.run(
                resolved, cancellation=cancellation, progress=progress, log=log
            )
        except Exception as exc:
            ended = current_timestamp()
            log(
                AttendanceLogEvent(
                    ended,
                    "ERROR",
                    f"Attendance adapter failed unexpectedly: {exc}",
                )
            )
            result = AttendanceRunResult(
                success=False,
                cancelled=False,
                job_id=resolved.job_id,
                workflow=resolved.workflow,
                started_at=started,
                ended_at=ended,
                output_root=resolved.output_root,
                job_folder=None,
                output_files=(),
                record_counts={},
                error_summary=str(exc),
            )
        final_status = (
            "CANCELLED"
            if result.cancelled
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
        counts = result.record_counts
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            repository.finish_job(
                module_code="ATTENDANCE",
                job_id=resolved.job_id,
                unified_status=final_status,
                finished_at=result.ended_at,
                duration_seconds=duration,
                success_count=counts.get("valid", 0),
                warning_count=result.warning_count,
                failed_count=counts.get("anomaly", 0) if not result.success else 0,
                error_message=result.error_summary,
                legacy_status="SUCCESS" if result.success else final_status,
            )
            repository.update_job_artifacts(
                job_pk,
                summary_json_path=str(result.summary_json_path)
                if result.summary_json_path
                else None,
                process_log_path=str(result.process_log_path)
                if result.process_log_path
                else None,
                source_summary=(
                    f"config={resolved.configuration_source}; raw={counts.get('raw', 0)}; "
                    f"valid={counts.get('valid', 0)}; anomaly={counts.get('anomaly', 0)}"
                ),
            )
            for item in result.output_files:
                if not item.path.exists():
                    continue
                repository.add_job_file(
                    JobFileRecord(
                        job_pk=job_pk,
                        file_role=item.file_type,
                        file_path=str(item.path),
                        file_size=item.path.stat().st_size
                        if item.path.is_file()
                        else None,
                        exists_at_last_check=True,
                        recorded_at=result.ended_at,
                        last_checked_at=result.ended_at,
                    )
                )
        return result

    def request_cancellation(
        self,
        resolved: AttendanceResolvedRequest,
        token: AttendanceCancellationToken,
    ) -> None:
        token.request()
        if resolved.database_path is None:
            return
        try:
            with self.factory.connect(resolved.database_path) as connection:
                # Serialize the cancellation marker with terminal completion so a
                # late CANCEL_REQUESTED task can never replace CANCELLED/FAILED.
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    "SELECT unified_status FROM job_history "
                    "WHERE module_code = 'ATTENDANCE' AND job_id = ?",
                    (resolved.job_id,),
                ).fetchone()
                if current is None or current["unified_status"] in _TERMINAL_STATUSES:
                    return
                JobRepository(connection).update_job_status(
                    module_code="ATTENDANCE",
                    job_id=resolved.job_id,
                    unified_status="PAUSED",
                    legacy_status="CANCEL_REQUESTED",
                    phase="CANCEL_REQUESTED",
                    message="Cancellation requested; waiting for safe checkpoint.",
                )
        except RepositoryError:
            # Cancellation may win the race before PENDING is inserted.
            return

    @staticmethod
    def _validate_period(start: str | None, end: str | None) -> None:
        if not start or not end:
            raise ValueError("Start Date dan End Date wajib diisi.")
        try:
            start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        except ValueError as exc:
            raise ValueError("Tanggal harus memakai format YYYY-MM-DD.") from exc
        if start_date > end_date:
            raise ValueError("Start Date tidak boleh setelah End Date.")

    @staticmethod
    def _validate_output_parent(path: Path) -> None:
        candidate = path
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if not candidate.is_dir() or not os.access(candidate, os.W_OK):
            raise ValueError("Output Root tidak memiliki parent folder yang writable.")

    @staticmethod
    def _new_job_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"UI-{timestamp}-{uuid.uuid4().hex[:6].upper()}"
