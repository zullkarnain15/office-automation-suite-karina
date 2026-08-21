"""UI7 orchestration for Comparison Result."""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone

from shared.database.time_utils import current_timestamp
from ui.utilities_models import (
    ComparisonRunResult,
    ComparisonResolvedRequest,
    UtilitiesJobPhase,
)
from ui.services._utilities_job_audit import UtilitiesJobAudit
from ui.services.utilities_service import UtilitiesService


class ComparisonResultService:
    def __init__(self, storage_service, adapter, factory=None) -> None:
        self.defaults = UtilitiesService(storage_service, factory)
        self.adapter = adapter
        self.audit = UtilitiesJobAudit(factory)

    def load_defaults(self):
        return self.defaults.load_defaults()

    def resolve_request(self, request) -> ComparisonResolvedRequest:
        defaults = self.load_defaults()
        if not defaults.database_available or defaults.database_path is None:
            raise RuntimeError(defaults.warning)
        if request.workflow not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")
        for label, path in (
            ("Attendance Source", request.attendance_source),
            ("Outlook Source", request.outlook_source),
        ):
            if not path.is_dir():
                raise ValueError(f"{label} tidak ditemukan atau bukan folder.")
        start = (
            defaults.period_start if request.use_global_period else request.period_start
        )
        end = defaults.period_end if request.use_global_period else request.period_end
        self._period(start, end)
        output = (
            defaults.output_root if request.use_global_output else request.output_root
        )
        self._output(output)
        return ComparisonResolvedRequest(
            self._job_id(),
            defaults.database_path,
            request.attendance_source,
            request.outlook_source,
            request.workflow,
            str(start),
            str(end),
            output,
            request.use_global_period,
            request.use_global_output,
        )

    def preflight(self, request, *, cancellation):
        resolved = self.resolve_request(request)
        return resolved, self.adapter.validate(resolved, cancellation)

    def run_job(self, resolved, validation, *, cancellation, progress, log):
        job_pk = self.audit.start(
            resolved.database_path,
            resolved,
            "COMPARISON_RESULT",
            f"attendance={resolved.attendance_source}; outlook={resolved.outlook_source}",
        )
        for phase, message in (
            (UtilitiesJobPhase.VALIDATION_COMPLETED, "Read-only validation completed."),
            (
                UtilitiesJobPhase.SOURCE_INSPECTION_STARTED,
                "Using inspected source snapshot.",
            ),
            (
                UtilitiesJobPhase.SOURCE_INSPECTION_COMPLETED,
                "Attendance and Outlook sources inspected.",
            ),
            (UtilitiesJobPhase.COMPARISON_STARTED, "Comparison engine started."),
            (
                UtilitiesJobPhase.REPORT_WRITING_STARTED,
                "Report generation stage started.",
            ),
        ):
            self.audit.event(resolved.database_path, resolved.job_id, phase, message)
        try:
            result = self.adapter.run(
                resolved,
                validation.scan,
                cancellation=cancellation,
                progress=progress,
                log=log,
            )
        except Exception as exc:
            now = current_timestamp()
            result = ComparisonRunResult(
                False,
                False,
                resolved.job_id,
                now,
                now,
                None,
                (),
                error_summary=str(exc),
            )
        if result.outputs:
            self.audit.event(
                resolved.database_path,
                resolved.job_id,
                UtilitiesJobPhase.OUTPUT_CREATED,
                "Existing output artifacts detected.",
            )
        self.audit.finish(resolved.database_path, job_pk, result)
        return result

    def request_cancellation(self, resolved, token) -> None:
        self.audit.cancel(resolved.database_path, resolved.job_id, token)

    @staticmethod
    def _period(start, end) -> None:
        try:
            first, last = date.fromisoformat(str(start)), date.fromisoformat(str(end))
        except ValueError as exc:
            raise ValueError("Tanggal harus memakai format YYYY-MM-DD.") from exc
        if first > last:
            raise ValueError("Start Date tidak boleh setelah End Date.")

    @staticmethod
    def _output(output) -> None:
        if output is None or not str(output).strip():
            raise ValueError("Output Root wajib diisi.")
        parent = output
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK):
            raise ValueError("Parent Output Root tidak writable.")

    @staticmethod
    def _job_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"UI-{stamp}-{uuid.uuid4().hex[:6].upper()}"
