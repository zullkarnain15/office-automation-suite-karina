"""UI5 Outlook Revisi request resolution and audited job lifecycle."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.exceptions import RepositoryError
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from shared.database.time_utils import current_timestamp
from shared.payroll_period import (
    normalize_payroll_period,
    payroll_period_dates,
)
from ui.outlook_revisi_models import (
    OutboundSafetyState,
    OutlookRevisiCancellationToken,
    OutlookRevisiDefaults,
    OutlookRevisiLogEvent,
    OutlookRevisiProgressEvent,
    OutlookRevisiResolvedRequest,
    OutlookRevisiRunRequest,
    OutlookRevisiRunResult,
)
from ui.services.module_configuration_service import ModuleConfigurationService

_TERMINAL_STATUSES = {
    "COMPLETED",
    "COMPLETED_WITH_WARNING",
    "FAILED",
    "CANCELLED",
    "NEED_REVIEW",
    "SKIPPED",
    "UPLOADED",
}


class OutlookRevisiService:
    def __init__(self, storage_service, adapter) -> None:
        self.storage_service = storage_service
        self.adapter = adapter
        self.factory = SQLiteConnectionFactory()
        self.module_configurations = ModuleConfigurationService(self.factory)

    def load_active_configuration(self):
        defaults = self.load_defaults()
        summaries = self.module_configurations.load_summaries(defaults.database_path)
        return next(item for item in summaries if item.module == "OUTLOOK_REVISI")

    def load_defaults(self) -> OutlookRevisiDefaults:
        storage = self.storage_service.resolve_status()
        database = storage.database_path
        if not storage.database_valid or database is None:
            return OutlookRevisiDefaults(
                False,
                database,
                warning=(
                    "Data Location belum disiapkan. Siapkan melalui Settings untuk "
                    "menjalankan Outlook Revisi dari Unified UI."
                ),
            )
        with self.factory.connect(database, read_only=True) as connection:
            global_value = GlobalSettingsRepository(connection).get_global_settings()
            module = connection.execute(
                "SELECT use_global_output, use_global_period, payroll_period, "
                "resubmit_deadline "
                "FROM outlook_settings LIMIT 1"
            ).fetchone()
        return OutlookRevisiDefaults(
            True,
            database,
            bool(module and module["use_global_output"]),
            bool(module and module["use_global_period"]),
            Path(global_value.output_root)
            if global_value and global_value.output_root
            else None,
            global_value.period_start if global_value else None,
            global_value.period_end if global_value else None,
            str(module["payroll_period"])
            if module and module["payroll_period"]
            else None,
            str(module["resubmit_deadline"])
            if module and module["resubmit_deadline"]
            else None,
        )

    def resolve_request(
        self,
        request: OutlookRevisiRunRequest,
        *,
        require_database: bool,
    ) -> OutlookRevisiResolvedRequest:
        if request.workflow not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")
        if request.configuration_path is not None:
            if request.configuration_path.suffix.casefold() != ".xlsx":
                raise ValueError("Outlook Revisi Configuration harus berupa file .xlsx.")
            if not request.configuration_path.is_file():
                raise ValueError("Outlook Revisi Configuration tidak ditemukan.")
        if request.message_limit is not None and request.message_limit <= 0:
            raise ValueError("Email Limit harus lebih besar dari nol.")
        defaults = self.load_defaults()
        if require_database and not defaults.database_available:
            raise RuntimeError(defaults.warning)
        if request.configuration_path is None and not defaults.database_available:
            raise RuntimeError(
                "Konfigurasi aktif SQLite belum tersedia. Gunakan fallback Excel "
                "atau siapkan database melalui Settings."
            )

        if request.payroll_period:
            payroll_period = normalize_payroll_period(request.payroll_period)
        elif defaults.payroll_period:
            payroll_period = normalize_payroll_period(defaults.payroll_period)
        else:
            payroll_period = self._legacy_request_payroll_period(request)
        start_date, end_date = payroll_period_dates(payroll_period)

        if request.use_global_output:
            output = defaults.global_output_root
            if not defaults.database_available or output is None:
                raise ValueError("Global output belum tersedia.")
        else:
            output = request.override_output_root
        if output is None or not str(output).strip():
            raise ValueError("Output Root wajib diisi.")
        output = output.expanduser()
        if output.name.casefold() == "output":
            output = output / "Outlook-Revisi"
        self._validate_output_parent(output)
        return OutlookRevisiResolvedRequest(
            job_id=self._new_job_id(),
            database_path=defaults.database_path
            if defaults.database_available
            else None,
            configuration_path=request.configuration_path,
            workflow=request.workflow,
            output_root=output,
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            payroll_period=payroll_period,
            used_global_output=request.use_global_output,
            used_global_period=False,
            dry_run=request.dry_run,
            message_limit=request.message_limit,
        )

    def preflight(
        self,
        request: OutlookRevisiRunRequest,
        *,
        require_database: bool,
        check_mailbox: bool,
    ):
        resolved = self.resolve_request(request, require_database=require_database)
        validation = self.adapter.validate(resolved, check_mailbox=check_mailbox)
        resolved = replace(
            resolved,
            outbound_requires_confirmation=(validation.outbound.requires_confirmation),
        )
        return resolved, validation

    def confirm_outbound(
        self,
        resolved: OutlookRevisiResolvedRequest,
        safety: OutboundSafetyState,
        *,
        acknowledged: bool,
        typed_confirmed: bool,
    ) -> OutlookRevisiResolvedRequest:
        if safety.requires_confirmation and not acknowledged:
            raise ValueError("Outbound safety checkbox wajib dikonfirmasi.")
        if safety.requires_confirmation and not typed_confirmed:
            raise ValueError("Typed confirmation SEND wajib diselesaikan.")
        return replace(
            resolved,
            outbound_requires_confirmation=safety.requires_confirmation,
            outbound_acknowledged=acknowledged,
            send_typed_confirmed=typed_confirmed,
        )

    def run_job(
        self,
        resolved: OutlookRevisiResolvedRequest,
        *,
        cancellation: OutlookRevisiCancellationToken,
        progress: Callable[[OutlookRevisiProgressEvent], None],
        log: Callable[[OutlookRevisiLogEvent], None],
    ) -> OutlookRevisiRunResult:
        if resolved.database_path is None:
            raise RuntimeError("Database audit Outlook Revisi tidak tersedia.")
        if resolved.outbound_requires_confirmation and not (
            resolved.outbound_acknowledged and resolved.send_typed_confirmed
        ):
            raise RuntimeError("Outbound safety confirmation belum lengkap.")

        started = current_timestamp()
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=resolved.job_id,
                    module_code="OUTLOOK_REVISI",
                    workflow=resolved.workflow,
                    unified_status="PENDING",
                    output_path_used=str(resolved.output_root),
                    period_start_used=resolved.period_start,
                    period_end_used=resolved.period_end,
                    used_global_output=resolved.used_global_output,
                    used_global_period=resolved.used_global_period,
                    source_summary=(
                        f"config={resolved.configuration_source}; "
                        "mailbox=karina.hr.1@oto.co.id; "
                        f"mode={'PREVIEW' if resolved.dry_run else 'LIVE'}"
                    ),
                    created_at=started,
                    started_at=started,
                )
            )
            if resolved.outbound_requires_confirmation:
                repository.update_job_status(
                    module_code="OUTLOOK_REVISI",
                    job_id=resolved.job_id,
                    unified_status="PENDING",
                    phase="OUTBOUND_CONFIRMED",
                    message="Outbound checkbox, typed confirmation, and final confirmation completed.",
                )
            repository.update_job_status(
                module_code="OUTLOOK_REVISI",
                job_id=resolved.job_id,
                unified_status="RUNNING",
                phase="ENGINE",
                message="Outlook Revisi engine started.",
            )
        try:
            result = self.adapter.run(
                resolved,
                cancellation=cancellation,
                progress=progress,
                log=log,
            )
        except Exception as exc:
            ended = current_timestamp()
            log(
                OutlookRevisiLogEvent(
                    ended,
                    "ERROR",
                    f"Outlook Revisi adapter failed unexpectedly: {exc}",
                )
            )
            result = OutlookRevisiRunResult(
                False,
                False,
                resolved.job_id,
                resolved.workflow,
                "karina.hr.1@oto.co.id",
                started,
                ended,
                resolved.output_root,
                None,
                {},
                {},
                {},
                (),
                error_summary=str(exc),
            )
        final_status = (
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
        counts = result.message_counts
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            repository.finish_job(
                module_code="OUTLOOK_REVISI",
                job_id=resolved.job_id,
                unified_status=final_status,
                finished_at=result.ended_at,
                duration_seconds=duration,
                success_count=counts.get("success", 0),
                warning_count=result.warning_count,
                failed_count=counts.get("failed", 0),
                skipped_count=counts.get("skipped", 0),
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
                    "mailbox=karina.hr.1@oto.co.id; "
                    f"total={counts.get('total', 0)}; "
                    f"success={counts.get('success', 0)}; "
                    f"failed={counts.get('failed', 0)}"
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
        resolved: OutlookRevisiResolvedRequest,
        token: OutlookRevisiCancellationToken,
    ) -> None:
        token.request()
        if resolved.database_path is None:
            return
        try:
            with self.factory.connect(resolved.database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    "SELECT unified_status FROM job_history "
                    "WHERE module_code='OUTLOOK_REVISI' AND job_id=?",
                    (resolved.job_id,),
                ).fetchone()
                if current is None or current["unified_status"] in _TERMINAL_STATUSES:
                    return
                JobRepository(connection).update_job_status(
                    module_code="OUTLOOK_REVISI",
                    job_id=resolved.job_id,
                    unified_status="PAUSED",
                    legacy_status="CANCEL_REQUESTED",
                    phase="CANCEL_REQUESTED",
                    message="Cancellation requested; waiting for safe checkpoint.",
                )
        except RepositoryError:
            return

    @staticmethod
    def _validate_period(start: str | None, end: str | None) -> tuple[date, date]:
        if not start or not end:
            raise ValueError("Start Date dan End Date wajib diisi.")
        try:
            start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        except ValueError as exc:
            raise ValueError("Tanggal harus memakai format YYYY-MM-DD.") from exc
        if start_date > end_date:
            raise ValueError("Start Date tidak boleh setelah End Date.")
        return start_date, end_date

    @classmethod
    def _legacy_request_payroll_period(
        cls,
        request: OutlookRevisiRunRequest,
    ) -> str:
        start_date, end_date = cls._validate_period(
            request.override_period_start,
            request.override_period_end,
        )
        if (start_date.year, start_date.month) != (
            end_date.year,
            end_date.month,
        ):
            raise ValueError(
                "Payroll Period Outlook wajib diisi melalui Settings dalam "
                "format MM-YYYY."
            )
        return start_date.strftime("%m-%Y")

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
        return f"UI-OUTLOOK-{timestamp}-{uuid.uuid4().hex[:6].upper()}"
