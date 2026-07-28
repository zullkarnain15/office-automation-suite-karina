"""UI7 orchestration for Attachment Consolidation."""

from __future__ import annotations

from shared.database.time_utils import current_timestamp
from ui.services._utilities_job_audit import UtilitiesJobAudit
from ui.services.comparison_result_service import ComparisonResultService
from ui.services.utilities_service import UtilitiesService
from ui.utilities_models import (
    AttachmentConsolidationResolvedRequest,
    AttachmentConsolidationRunResult,
    UtilitiesJobPhase,
)


class AttachmentConsolidationService:
    def __init__(self, storage_service, adapter, factory=None) -> None:
        self.defaults = UtilitiesService(storage_service, factory)
        self.adapter = adapter
        self.audit = UtilitiesJobAudit(factory)

    def load_defaults(self):
        return self.defaults.load_defaults()

    def resolve_request(self, request) -> AttachmentConsolidationResolvedRequest:
        defaults = self.load_defaults()
        if not defaults.database_available or defaults.database_path is None:
            raise RuntimeError(defaults.warning)
        if request.workflow not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")
        if request.mode not in {"EXCEL", "TXT"}:
            raise ValueError("Mode attachment harus EXCEL atau TXT.")
        if not request.source_folder.is_dir():
            raise ValueError("Source Folder tidak ditemukan atau bukan folder.")
        output = (
            defaults.output_root if request.use_global_output else request.output_root
        )
        ComparisonResultService._output(output)
        if request.source_folder.resolve() == output.resolve():
            raise ValueError("Source Folder dan Output Root tidak boleh sama.")
        max_lines = request.txt_max_lines_override or defaults.attachment_txt_max_lines
        if max_lines <= 0:
            raise ValueError("TXT Max Lines harus lebih dari nol.")
        return AttachmentConsolidationResolvedRequest(
            ComparisonResultService._job_id(),
            defaults.database_path,
            request.source_folder,
            request.workflow,
            request.mode,
            request.scan_subfolders,
            output,
            request.use_global_output,
            max_lines,
        )

    def preflight(self, request, *, cancellation):
        resolved = self.resolve_request(request)
        return resolved, self.adapter.validate(resolved, cancellation)

    def run_job(self, resolved, validation, *, cancellation, progress, log):
        job_pk = self.audit.start(
            resolved.database_path,
            resolved,
            "ATTACHMENT_CONSOLIDATION",
            f"source={resolved.source_folder}; mode={resolved.mode}",
        )
        for phase, message in (
            (UtilitiesJobPhase.VALIDATION_COMPLETED, "Read-only validation completed."),
            (
                UtilitiesJobPhase.SOURCE_SCAN_STARTED,
                "Using explicit source scan snapshot.",
            ),
            (
                UtilitiesJobPhase.SOURCE_SCAN_COMPLETED,
                "Attachment source scan completed.",
            ),
            (UtilitiesJobPhase.CONSOLIDATION_STARTED, "Consolidation engine started."),
            (UtilitiesJobPhase.TXT_WRITING_STARTED, "TXT generation stage started."),
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
            result = AttachmentConsolidationRunResult(
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
