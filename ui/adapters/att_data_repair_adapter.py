"""UI boundary for the Att Data Repair engine."""

from __future__ import annotations

import re
from pathlib import Path

from shared.database.time_utils import current_timestamp
from ui.utilities_models import (
    AttDataRepairCancellationToken,
    AttDataRepairLogEvent,
    AttDataRepairOutputFile,
    AttDataRepairProgressEvent,
    AttDataRepairResolvedRequest,
    AttDataRepairRunResult,
    AttDataRepairValidationResult,
    UtilitiesFileRole,
)
from utilities.att_data_repair.artifacts import (
    AttDataRepairJobRequest,
    AttDataRepairJobResult,
)
from utilities.att_data_repair.engine import AttDataRepairEngine
from utilities.att_data_repair.models import (
    MissingRequiredColumnError,
    MissingRequiredSheetError,
    SourceWorkbookError,
)
from utilities.att_data_repair.report_reader import AttDataRepairReportReader
from utilities.att_data_repair.statuses import JobStatus


class AttDataRepairAdapter:
    """Preflight source workbooks and run Att Data Repair without UI widgets."""

    def __init__(
        self,
        engine: AttDataRepairEngine | None = None,
        reader: AttDataRepairReportReader | None = None,
    ) -> None:
        self.engine = engine or AttDataRepairEngine()
        self.reader = reader or AttDataRepairReportReader()

    def validate(
        self,
        resolved: AttDataRepairResolvedRequest,
        cancellation: AttDataRepairCancellationToken,
    ) -> AttDataRepairValidationResult:
        if cancellation.requested:
            return AttDataRepairValidationResult(
                False,
                0,
                0,
                0,
                resolved.output_root,
                errors=("Validasi dibatalkan.",),
            )
        try:
            records = self.reader.read(resolved.source_report)
        except MissingRequiredSheetError:
            return _invalid(
                resolved.output_root,
                "Sheet Valid_Records atau Invalid_Records tidak ditemukan pada report sumber.",
            )
        except MissingRequiredColumnError:
            return _invalid(
                resolved.output_root,
                "Struktur report sumber tidak sesuai karena kolom wajib tidak ditemukan.",
            )
        except SourceWorkbookError:
            return _invalid(
                resolved.output_root,
                "File sumber tidak dapat dibaca sebagai Excel Report Attachment Consolidation.",
            )
        valid_count = _sheet_count(records, "Valid_Records")
        invalid_count = _sheet_count(records, "Invalid_Records")
        discovery = resolved.discovery
        warnings = _discovery_warnings(discovery, resolved.source_report)
        return AttDataRepairValidationResult(
            bool(records),
            len(records),
            valid_count,
            invalid_count,
            resolved.output_root,
            warnings=warnings,
            errors=() if records else ("Tidak ada record sumber untuk diproses.",),
            scan=records,
            discovery_files_scanned=getattr(discovery, "files_scanned", 0),
            discovered_valid_reports=len(getattr(discovery, "valid_candidates", ())),
            discovered_invalid_reports=len(
                getattr(discovery, "invalid_candidates", ())
            ),
        )

    def run(
        self,
        resolved: AttDataRepairResolvedRequest,
        job_request: AttDataRepairJobRequest,
        *,
        cancellation: AttDataRepairCancellationToken,
        progress,
        log,
    ) -> tuple[AttDataRepairRunResult, AttDataRepairJobResult | None]:
        started = current_timestamp()
        if cancellation.requested:
            return (
                AttDataRepairRunResult(
                    False,
                    True,
                    resolved.job_id,
                    started,
                    started,
                    None,
                    (),
                    status="CANCELLED",
                    error_summary="Job dibatalkan sebelum engine dimulai.",
                ),
                None,
            )

        _emit(progress, 25, "Membaca Valid_Records dan Invalid_Records")
        _log(log, "INFO", "PREFLIGHT", "Preflight source passed.")
        _emit(progress, 45, "Normalisasi dan repair")
        _log(log, "INFO", "ENGINE", "Att Data Repair dimulai.")
        result = self.engine.run_job(job_request)
        _emit(progress, 70, "Membuat TXT" if resolved.generate_txt else "TXT dilewati")
        _emit(
            progress,
            85,
            "Membuat Excel report"
            if resolved.generate_excel_report
            else "Excel report dilewati",
        )
        _emit(progress, 95, "Menulis log, summary, dan history")
        ui_result = self._ui_result(result)
        _log(log, "INFO", "COMPLETE", f"Job status: {ui_result.status}.")
        _emit(progress, 100, "Selesai")
        return ui_result, result

    @staticmethod
    def _ui_result(result: AttDataRepairJobResult) -> AttDataRepairRunResult:
        analysis = result.analysis_result
        outputs: list[AttDataRepairOutputFile] = [
            AttDataRepairOutputFile(UtilitiesFileRole.OUTPUT_FOLDER, result.paths.job_folder)
        ]
        outputs.extend(
            AttDataRepairOutputFile(UtilitiesFileRole.HRIS_TXT, item.file_path)
            for item in result.txt_artifacts
            if item.file_path.exists()
        )
        if result.report_artifact and result.report_artifact.file_path.exists():
            outputs.append(
                AttDataRepairOutputFile(
                    UtilitiesFileRole.EXCEL_REPORT,
                    result.report_artifact.file_path,
                )
            )
        for role, path in (
            (UtilitiesFileRole.PROCESS_LOG, result.paths.process_log),
            (UtilitiesFileRole.SUMMARY_JSON, result.paths.summary_json),
            (
                UtilitiesFileRole.SOURCE_REPORT,
                result.analysis_result.source_records[0].source_workbook
                if result.analysis_result.source_records
                else None,
            ),
        ):
            if path is not None and Path(path).exists():
                outputs.append(AttDataRepairOutputFile(role, Path(path)))
        status = str(result.status)
        return AttDataRepairRunResult(
            status in {JobStatus.SUCCESS, JobStatus.PARTIAL_SUCCESS, JobStatus.NO_VALID_RECORDS},
            False,
            result.job_id,
            result.started_at.isoformat(timespec="seconds"),
            result.completed_at.isoformat(timespec="seconds"),
            result.paths.job_folder,
            tuple(outputs),
            source_records=analysis.source_counts.get("total", 0),
            final_records=len(analysis.final_records),
            changed_records=len(analysis.changed_records),
            anomaly_records=len(analysis.anomalies),
            txt_file_count=len(result.txt_artifacts),
            report_generated=result.report_artifact is not None,
            warning_count=len(analysis.anomalies)
            + int(status == JobStatus.NO_VALID_RECORDS),
            status=status,
            error_summary=result.error_message,
        )


def _invalid(output_root: Path, message: str) -> AttDataRepairValidationResult:
    return AttDataRepairValidationResult(False, 0, 0, 0, output_root, errors=(message,))


def _discovery_warnings(discovery, selected_report: Path) -> tuple[str, ...]:
    if discovery is None:
        return ()
    invalid = len(discovery.invalid_candidates)
    skipped = discovery.skipped_temp_files
    lines = [
        "Folder scan: "
        f"{discovery.files_scanned} Excel file, "
        f"{len(discovery.valid_candidates)} valid, "
        f"{invalid} invalid; selected {Path(selected_report).name}."
    ]
    if skipped:
        lines.append(f"Skipped temporary Excel files: {skipped}.")
    if invalid:
        lines.extend(
            f"Invalid report: {candidate.relative_path} - {candidate.reason}"
            for candidate in discovery.invalid_candidates[:5]
        )
    return tuple(lines)


def _sheet_count(records, expected: str) -> int:
    expected_name = _normalize_name(expected)
    return sum(
        1 for record in records if _normalize_name(record.source_sheet) == expected_name
    )


def _normalize_name(value: object) -> str:
    return re.sub(r"[\s_]+", "", str(value or "")).casefold()


def _emit(progress, current: int, message: str) -> None:
    progress(AttDataRepairProgressEvent(str(current), message, current, 100))


def _log(log, level: str, stage: str, message: str) -> None:
    log(AttDataRepairLogEvent(current_timestamp(), level, stage, message))
