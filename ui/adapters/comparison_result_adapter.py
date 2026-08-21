"""UI7 boundary for the existing Attendance reconciliation engine."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from shared.database.time_utils import current_timestamp
from ui.utilities_models import (
    ComparisonCancellationToken,
    ComparisonLogEvent,
    ComparisonOutputFile,
    ComparisonProgressEvent,
    ComparisonResolvedRequest,
    ComparisonRunResult,
    ComparisonValidationResult,
    UtilitiesFileRole,
)
from utilities.attendance_reconciliation.engine import ReconciliationEngine
from utilities.attendance_reconciliation.models import (
    ALL_COMPARISON_STATUSES,
    SOURCE_MODE_SCAN,
    ReconciliationCancelled,
    ReconciliationRequest,
)


class ComparisonResultAdapter:
    def __init__(self, engine: ReconciliationEngine | None = None) -> None:
        self.engine = engine or ReconciliationEngine()

    def validate(
        self,
        resolved: ComparisonResolvedRequest,
        cancellation: ComparisonCancellationToken,
    ) -> ComparisonValidationResult:
        scan = self.engine.scan(
            self._engine_request(resolved),
            cancellation.event,
            read_only=True,
        )
        invalid = len(scan.attendance.invalid_records) + len(
            scan.outlook.invalid_records
        )
        warnings = tuple(scan.warnings)
        if invalid:
            warnings += (f"{invalid} record sumber tidak valid ditemukan.",)
        return ComparisonValidationResult(
            valid=scan.attendance.reports_used > 0,
            attendance_reports=scan.attendance.reports_used,
            outlook_reports=scan.outlook.reports_used,
            expected_report_name="Comparison_Attendance_Reconciliation_*.xlsx",
            warnings=warnings,
            scan=scan,
        )

    def run(
        self,
        resolved: ComparisonResolvedRequest,
        scan: object,
        *,
        cancellation: ComparisonCancellationToken,
        progress,
        log,
    ) -> ComparisonRunResult:
        started = current_timestamp()
        progress(ComparisonProgressEvent("engine", "Memulai comparison...", 0, 1))
        log(ComparisonLogEvent(started, "INFO", "ENGINE", "Comparison dimulai."))
        try:
            result = self.engine.run(
                self._engine_request(resolved),
                scan=scan,
                cancel_event=cancellation.event,
            )
        except ReconciliationCancelled as exc:
            ended = current_timestamp()
            log(ComparisonLogEvent(ended, "WARNING", "CANCELLED", str(exc)))
            return ComparisonRunResult(
                False,
                True,
                resolved.job_id,
                started,
                ended,
                None,
                (),
                error_summary=str(exc),
            )
        ended = current_timestamp()
        counts = Counter(item.status for item in result.comparisons)
        breakdown = tuple(
            (status, counts[status]) for status in ALL_COMPARISON_STATUSES
        )
        invalid = counts["INVALID_SOURCE_DATA"]
        attention = sum(item.review_required for item in result.comparisons)
        outputs = self._outputs(result)
        progress(ComparisonProgressEvent("complete", "Comparison selesai.", 1, 1))
        log(ComparisonLogEvent(ended, "INFO", "COMPLETE", "Comparison selesai."))
        return ComparisonRunResult(
            result.success,
            result.cancelled,
            resolved.job_id,
            started,
            ended,
            result.output_folder,
            outputs,
            total_records=len(result.comparisons),
            attention_count=attention,
            conflict_count=len(result.conflicts),
            invalid_count=invalid,
            warning_count=len(result.warnings),
            status_breakdown=breakdown,
            error_summary=result.error_message or None,
        )

    @staticmethod
    def _engine_request(resolved: ComparisonResolvedRequest) -> ReconciliationRequest:
        return ReconciliationRequest(
            source_mode=SOURCE_MODE_SCAN,
            workflow="Branch" if resolved.workflow == "BRANCH" else "HO",
            attendance_path=resolved.attendance_source,
            outlook_path=resolved.outlook_source,
            start_date=date.fromisoformat(resolved.period_start),
            end_date=date.fromisoformat(resolved.period_end),
            output_folder=resolved.output_root,
        )

    @staticmethod
    def _outputs(result) -> tuple[ComparisonOutputFile, ...]:
        candidates = (
            (UtilitiesFileRole.OUTPUT_FOLDER, result.output_folder),
            (UtilitiesFileRole.COMPARISON_REPORT, result.report_file),
            (UtilitiesFileRole.PROCESS_LOG, result.process_log),
            (UtilitiesFileRole.SUMMARY_JSON, result.summary_json),
            (
                UtilitiesFileRole.SOURCE_ATTENDANCE_REFERENCE,
                result.scan.fingerprint[2] if result.scan.fingerprint else None,
            ),
            (
                UtilitiesFileRole.SOURCE_OUTLOOK_REFERENCE,
                result.scan.fingerprint[3] if result.scan.fingerprint else None,
            ),
        )
        return tuple(
            ComparisonOutputFile(role, Path(path))
            for role, path in candidates
            if path is not None and Path(path).exists()
        )
