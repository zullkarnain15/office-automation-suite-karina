"""UI7 boundary for the existing Attachment Consolidation engine."""

from __future__ import annotations

from collections import Counter
from shared.database.time_utils import current_timestamp
from ui.utilities_models import (
    AttachmentConsolidationCancellationToken,
    AttachmentConsolidationLogEvent,
    AttachmentConsolidationOutputFile,
    AttachmentConsolidationProgressEvent,
    AttachmentConsolidationResolvedRequest,
    AttachmentConsolidationRunResult,
    AttachmentConsolidationValidationResult,
    UtilitiesFileRole,
)
from utilities.attachment_consolidation.engine import AttachmentConsolidationEngine
from utilities.attachment_consolidation.models import (
    MODE_EXCEL,
    MODE_TXT,
    ConsolidationRequest,
)


class AttachmentConsolidationAdapter:
    def __init__(self, engine: AttachmentConsolidationEngine | None = None) -> None:
        self.engine = engine or AttachmentConsolidationEngine()

    def validate(
        self,
        resolved: AttachmentConsolidationResolvedRequest,
        cancellation: AttachmentConsolidationCancellationToken,
    ) -> AttachmentConsolidationValidationResult:
        scan = self.engine.scan(self._engine_request(resolved), cancellation.event)
        processable = scan.processable_files
        names = Counter(item.path.name.casefold() for item in processable)
        duplicates = sum(count - 1 for count in names.values() if count > 1)
        subfolders = {
            item.path.parent.resolve()
            for item in scan.files
            if item.path.parent.resolve() != resolved.source_folder.resolve()
        }
        invalid = len(scan.files) - len(processable)
        errors = () if processable else ("Tidak ada file yang dapat diproses.",)
        return AttachmentConsolidationValidationResult(
            valid=bool(processable),
            total_files=len(scan.files),
            processable_files=len(processable),
            invalid_files=invalid,
            duplicate_candidates=duplicates,
            subfolder_count=len(subfolders),
            txt_max_lines=resolved.txt_max_lines,
            expected_output_root=resolved.output_root,
            warnings=tuple(scan.warnings),
            errors=errors,
            scan=scan,
        )

    def run(
        self,
        resolved: AttachmentConsolidationResolvedRequest,
        scan: object,
        *,
        cancellation: AttachmentConsolidationCancellationToken,
        progress,
        log,
    ) -> AttachmentConsolidationRunResult:
        started = current_timestamp()

        def engine_progress(stage, current, total, message):
            progress(
                AttachmentConsolidationProgressEvent(stage, message, current, total)
            )

        log(
            AttachmentConsolidationLogEvent(
                started, "INFO", "ENGINE", "Konsolidasi dimulai."
            )
        )
        result = self.engine.run(
            self._engine_request(resolved),
            scan=scan,
            cancel_event=cancellation.event,
            progress=engine_progress,
            txt_max_lines=resolved.txt_max_lines,
        )
        outputs = [
            AttachmentConsolidationOutputFile(UtilitiesFileRole.CONSOLIDATED_TXT, path)
            for path in result.output_files
            if path.exists()
        ]
        for role, path in (
            (UtilitiesFileRole.OUTPUT_FOLDER, result.artifacts.job_folder),
            (UtilitiesFileRole.CONSOLIDATION_REPORT, result.artifacts.report_file),
            (UtilitiesFileRole.PROCESS_LOG, result.artifacts.process_log),
            (UtilitiesFileRole.SUMMARY_JSON, result.artifacts.summary_json),
            (UtilitiesFileRole.SOURCE_ATTACHMENT_FOLDER, result.request.source_root),
        ):
            if path.exists():
                outputs.append(AttachmentConsolidationOutputFile(role, path))
        ended = result.finished_at.isoformat(timespec="seconds")
        log(
            AttachmentConsolidationLogEvent(
                ended, "INFO", "COMPLETE", "Konsolidasi selesai."
            )
        )
        rejected = sum(not item.scanned.processable for item in result.file_results)
        return AttachmentConsolidationRunResult(
            result.success,
            result.cancelled,
            resolved.job_id,
            result.started_at.isoformat(timespec="seconds"),
            ended,
            result.artifacts.job_folder,
            tuple(outputs),
            files_scanned=len(result.scan.files),
            files_accepted=len(result.scan.processable_files),
            files_rejected=rejected,
            duplicates=0,
            output_txt_count=len(result.output_files),
            report_count=int(result.artifacts.report_file.exists()),
            warning_count=len(result.scan.warnings) + len(result.anomalies),
            error_summary=result.error_message or None,
        )

    @staticmethod
    def _engine_request(
        resolved: AttachmentConsolidationResolvedRequest,
    ) -> ConsolidationRequest:
        mode = MODE_EXCEL if resolved.mode == "EXCEL" else MODE_TXT
        return ConsolidationRequest(
            mode=mode,
            workflow="Branch" if resolved.workflow == "BRANCH" else "HO",
            source_root=resolved.source_folder,
            output_root=resolved.output_root,
            scan_subfolders=resolved.scan_subfolders,
        )
