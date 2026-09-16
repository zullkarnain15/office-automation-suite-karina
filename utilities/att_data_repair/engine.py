"""In-memory analysis and non-GUI job orchestration for Att Data Repair."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from utilities.att_data_repair.artifacts import (
    AttDataRepairJobRequest,
    AttDataRepairJobResult,
    JobPaths,
    ReportArtifact,
    TxtWriteResult,
)
from utilities.att_data_repair.constants import (
    ENGINE_VERSION,
    FEATURE_NAME,
    INVALID_RECORDS_SHEET,
    SUMMARY_SCHEMA_VERSION,
    VALID_RECORDS_SHEET,
    WORKFLOW_BRANCH,
    WORKFLOW_HO,
)
from utilities.att_data_repair.job_manager import AttDataRepairJobManager
from utilities.att_data_repair.models import (
    AttDataRepairAnalysisResult,
    AttDataRepairRequest,
    AttDataRepairError,
    RepairAnomaly,
    SourceRecord,
)
from utilities.att_data_repair.normalizer import normalize_record
from utilities.att_data_repair.process_logger import AttDataRepairProcessLogger
from utilities.att_data_repair.repair_rules import apply_repair_rules
from utilities.att_data_repair.report_reader import AttDataRepairReportReader
from utilities.att_data_repair.report_writer import AttDataRepairReportWriter
from utilities.att_data_repair.statuses import AnomalyCode, JobStatus
from utilities.att_data_repair.summary_writer import AttDataRepairSummaryWriter
from utilities.att_data_repair.txt_writer import AttDataRepairTxtWriter
from utilities.att_data_repair.validator import validate_request


class AttDataRepairEngine:
    """Analyze AC reports and optionally run the Sprint 3 output pipeline."""

    def __init__(
        self,
        reader: AttDataRepairReportReader | None = None,
        job_manager: AttDataRepairJobManager | None = None,
        txt_writer: AttDataRepairTxtWriter | None = None,
        report_writer: AttDataRepairReportWriter | None = None,
        summary_writer: AttDataRepairSummaryWriter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.clock = clock or datetime.now
        self.reader = reader or AttDataRepairReportReader()
        self.job_manager = job_manager or AttDataRepairJobManager(self.clock)
        self.txt_writer = txt_writer or AttDataRepairTxtWriter()
        self.report_writer = report_writer or AttDataRepairReportWriter()
        self.summary_writer = summary_writer or AttDataRepairSummaryWriter()

    def analyze(
        self,
        request: AttDataRepairRequest,
    ) -> AttDataRepairAnalysisResult:
        """Run Sprint 2 pipeline and return an in-memory result."""

        validate_request(request)
        source_records = self.reader.read(request.source_report)
        return self._analyze_records(request, source_records)

    def run_job(
        self,
        request: AttDataRepairJobRequest,
    ) -> AttDataRepairJobResult:
        """Run analysis and write TXT, Process.log, and summary.json."""

        validate_request(request.analysis_request)
        if not request.generate_txt and not request.generate_excel_report:
            raise ValueError(
                "Minimal salah satu output Att Data Repair harus aktif: "
                "Generate_TXT atau Generate_Excel_Report."
            )
        self._validate_output_root(request.output_root)
        source_records = self.reader.read(request.analysis_request.source_report)
        paths = self.job_manager.reserve(request.output_root)
        started_at = self.clock()
        logger = AttDataRepairProcessLogger(paths.process_log, self.clock)
        logger.info("Job started.")
        logger.info(f"Job ID: {paths.job_id}")
        logger.info(f"Engine version: {ENGINE_VERSION}")
        logger.info(f"Source report: {request.analysis_request.source_report}")
        logger.info(
            "Period: "
            f"{request.analysis_request.period_start.isoformat()} - "
            f"{request.analysis_request.period_end.isoformat()}"
        )
        logger.info(f"Output root: {request.output_root}")
        logger.info("Reader started.")

        analysis = AttDataRepairAnalysisResult()
        txt_result = TxtWriteResult()
        report_artifact: ReportArtifact | None = None
        status = JobStatus.FAILED
        error_message = None
        try:
            logger.info("Reader completed.")
            analysis = self._analyze_records(request.analysis_request, source_records)
            self._log_analysis(logger, analysis)
            status = self._job_status(analysis)
            if analysis.final_records and request.generate_txt:
                txt_result = self.txt_writer.write(
                    analysis.final_records,
                    paths.txt_folder,
                    max_rows_per_file=request.txt_max_rows_per_file,
                )
                logger.info(f"TXT unique code: {txt_result.unique_code}")
                for artifact in txt_result.artifacts:
                    logger.info(
                        f"TXT generated: {artifact.file_name}; "
                        f"rows={artifact.row_count}"
                    )
            elif analysis.final_records:
                logger.info("TXT generation skipped by configuration.")
            else:
                logger.warning("No final records. TXT generation skipped.")
            if request.generate_excel_report:
                logger.info("Report generation started.")
                report_artifact = self.report_writer.write(
                    report_folder=paths.report_folder,
                    job_id=paths.job_id,
                    status=str(status),
                    request=request,
                    paths=paths,
                    analysis=analysis,
                    txt_artifacts=txt_result.artifacts,
                    record_txt_assignment=txt_result.record_txt_assignment,
                    generated_at=self.clock(),
                )
                logger.info(f"Report generated: {report_artifact.file_name}")
                logger.info(
                    "Report sheets: " + ", ".join(report_artifact.sheet_names)
                )
                logger.info(f"Report size: {report_artifact.file_size_bytes} bytes")
            else:
                logger.info("Report generation skipped by configuration.")
            completed_at = self.clock()
            duration_seconds = max(
                0.0,
                (completed_at - started_at).total_seconds(),
            )
            logger.info(
                "Job duration: "
                f"{duration_seconds:.2f} seconds "
                f"({duration_seconds / 60:.2f} minutes)"
            )
            result = AttDataRepairJobResult(
                job_id=paths.job_id,
                status=str(status),
                paths=paths,
                analysis_result=analysis,
                txt_artifacts=txt_result.artifacts,
                record_txt_assignment=txt_result.record_txt_assignment,
                started_at=started_at,
                completed_at=completed_at,
                error_message=None,
                report_artifact=report_artifact,
            )
            self.summary_writer.write(
                paths.summary_json,
                self._summary_payload(
                    result,
                    request,
                    txt_result,
                ),
            )
            logger.info(f"Job status: {status}")
            logger.info("Job completed.")
            return result
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            completed_at = self.clock()
            logger.error(error_message)
            result = AttDataRepairJobResult(
                job_id=paths.job_id,
                status=str(JobStatus.FAILED),
                paths=paths,
                analysis_result=analysis,
                txt_artifacts=txt_result.artifacts,
                record_txt_assignment=txt_result.record_txt_assignment,
                started_at=started_at,
                completed_at=completed_at,
                error_message=error_message,
                report_artifact=report_artifact,
            )
            try:
                self.summary_writer.write(
                    paths.summary_json,
                    self._summary_payload(result, request, txt_result),
                )
            except AttDataRepairError as summary_error:
                logger.error(f"Failed summary could not be written: {summary_error}")
            logger.info(f"Job status: {JobStatus.FAILED}")
            logger.error("Job failed.")
            return result

    def _analyze_records(
        self,
        request: AttDataRepairRequest,
        source_records: tuple[SourceRecord, ...],
    ) -> AttDataRepairAnalysisResult:
        final_records = []
        anomalies = []
        change_log = []
        duplicate_eligible: dict[str, bool] = {}
        source_counts: Counter[str] = Counter()
        analysis_year = self.clock().year

        for source in source_records:
            source_counts[source.source_sheet] += 1
            normalized = normalize_record(source, request)
            final, anomaly, changes = apply_repair_rules(
                normalized,
                request,
                current_year=analysis_year,
            )
            if final is not None:
                final_records.append(final)
                duplicate_eligible[final.record_id] = _duplicate_eligible(normalized)
            if anomaly is not None:
                anomalies.append(anomaly)
            change_log.extend(changes)

        final_records, duplicate_anomalies = _remove_complete_duplicates(
            final_records,
            source_records,
            duplicate_eligible,
        )
        anomalies.extend(duplicate_anomalies)
        changed_records = tuple(record for record in final_records if record.changes)
        source_counts["total"] = len(source_records)
        return AttDataRepairAnalysisResult(
            final_records=tuple(final_records),
            changed_records=changed_records,
            anomalies=tuple(anomalies),
            change_log=tuple(change_log),
            source_counts=dict(source_counts),
            status_counts=self._status_counts(final_records, anomalies, change_log),
            source_records=source_records,
        )

    @staticmethod
    def _validate_output_root(output_root: Path) -> None:
        root = Path(output_root)
        candidate = root
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError(f"Output Root parent tidak valid: {output_root}")

    @staticmethod
    def _job_status(analysis: AttDataRepairAnalysisResult) -> JobStatus:
        if not analysis.final_records:
            return JobStatus.NO_VALID_RECORDS
        if analysis.anomalies:
            return JobStatus.PARTIAL_SUCCESS
        return JobStatus.SUCCESS

    @staticmethod
    def _log_analysis(
        logger: AttDataRepairProcessLogger,
        analysis: AttDataRepairAnalysisResult,
    ) -> None:
        logger.info(
            "Source counts: "
            f"{VALID_RECORDS_SHEET}={analysis.source_counts.get(VALID_RECORDS_SHEET, 0)}; "
            f"{INVALID_RECORDS_SHEET}={analysis.source_counts.get(INVALID_RECORDS_SHEET, 0)}; "
            f"total={analysis.source_counts.get('total', 0)}"
        )
        logger.info(
            "Analysis counts: "
            f"final={len(analysis.final_records)}; "
            f"changed={len(analysis.changed_records)}; "
            f"anomaly={len(analysis.anomalies)}"
        )
        workflow_counts = Counter(record.workflow for record in analysis.final_records)
        logger.info(
            "Workflow counts: "
            f"HO={workflow_counts[WORKFLOW_HO]}; "
            f"Branch={workflow_counts[WORKFLOW_BRANCH]}"
        )
        anomaly_counts = Counter(item.anomaly_code for item in analysis.anomalies)
        for code, count in sorted(anomaly_counts.items()):
            logger.warning(f"Anomaly {code}: {count}")

    @staticmethod
    def _summary_payload(
        result: AttDataRepairJobResult,
        request: AttDataRepairJobRequest,
        txt_result: TxtWriteResult,
    ) -> dict[str, object]:
        analysis = result.analysis_result
        workflow_counts = Counter(record.workflow for record in analysis.final_records)
        anomaly_counts = Counter(item.anomaly_code for item in analysis.anomalies)
        change_counts = Counter(item.change_code for item in analysis.change_log)
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "module": FEATURE_NAME,
            "engine_version": ENGINE_VERSION,
            "job_id": result.job_id,
            "status": result.status,
            "started_at": result.started_at.isoformat(timespec="seconds"),
            "completed_at": result.completed_at.isoformat(timespec="seconds"),
            "duration_seconds": round(
                max(0.0, (result.completed_at - result.started_at).total_seconds()),
                2,
            ),
            "duration_minutes": round(
                max(0.0, (result.completed_at - result.started_at).total_seconds())
                / 60,
                2,
            ),
            "period": {
                "start": request.analysis_request.period_start.isoformat(),
                "end": request.analysis_request.period_end.isoformat(),
            },
            "source": {
                "workbook": str(request.analysis_request.source_report),
                "sheets": [VALID_RECORDS_SHEET, INVALID_RECORDS_SHEET],
            },
            "output": _paths_payload(result.paths),
            "counts": {
                "source_total": analysis.source_counts.get("total", 0),
                "source_valid_sheet": analysis.source_counts.get(
                    VALID_RECORDS_SHEET,
                    0,
                ),
                "source_invalid_sheet": analysis.source_counts.get(
                    INVALID_RECORDS_SHEET,
                    0,
                ),
                "final_total": len(analysis.final_records),
                "changed_total": len(analysis.changed_records),
                "anomaly_total": len(analysis.anomalies),
                "workflow": {
                    WORKFLOW_HO: workflow_counts[WORKFLOW_HO],
                    WORKFLOW_BRANCH: workflow_counts[WORKFLOW_BRANCH],
                },
                "anomaly_by_code": dict(sorted(anomaly_counts.items())),
                "change_by_code": dict(sorted(change_counts.items())),
            },
            "txt": {
                "generated": bool(result.txt_artifacts),
                "reason": None
                if result.txt_artifacts
                else _txt_skip_reason(result, request),
                "max_rows_per_file": request.txt_max_rows_per_file,
                "unique_code": txt_result.unique_code,
                "file_count": len(result.txt_artifacts),
                "files": [
                    {
                        "workflow": item.workflow,
                        "sequence": item.sequence,
                        "file_name": item.file_name,
                        "row_count": item.row_count,
                    }
                    for item in result.txt_artifacts
                ],
            },
            "report": {
                **_report_payload(result),
            },
            "error": result.error_message,
        }

    @staticmethod
    def _source_counts(source_records) -> dict[str, int]:
        counts = Counter(record.source_sheet for record in source_records)
        counts["total"] = len(source_records)
        return dict(counts)

    @staticmethod
    def _status_counts(final_records, anomalies, changes) -> dict[str, int]:
        counts = Counter(record.final_status for record in final_records)
        counts.update(anomaly.anomaly_code for anomaly in anomalies)
        counts.update(change.change_code for change in changes)
        return dict(counts)


def _paths_payload(paths: JobPaths) -> dict[str, str]:
    return {
        "job_folder": str(paths.job_folder),
        "txt_folder": str(paths.txt_folder),
        "report_folder": str(paths.report_folder),
        "process_log": str(paths.process_log),
        "summary_json": str(paths.summary_json),
    }


def _report_payload(result: AttDataRepairJobResult) -> dict[str, object]:
    artifact = result.report_artifact
    if artifact is None:
        return {
            "generated": False,
            "reason": result.error_message or "Excel report disabled by configuration.",
        }
    return {
        "generated": True,
        "file_name": artifact.file_name,
        "file_path": str(artifact.file_path),
        "file_size_bytes": artifact.file_size_bytes,
        "sheet_count": len(artifact.sheet_names),
        "sheets": [
            {
                "name": name,
                "row_count": artifact.sheet_row_counts.get(name, 0),
            }
            for name in artifact.sheet_names
        ],
    }


def _txt_skip_reason(
    result: AttDataRepairJobResult,
    request: AttDataRepairJobRequest,
) -> str | None:
    if result.txt_artifacts:
        return None
    if not request.generate_txt:
        return "TXT generation disabled by configuration."
    if not result.analysis_result.final_records:
        return "No final records."
    return None


def _duplicate_eligible(record) -> bool:
    source = record.source
    raw_values = (
        source.nik_raw,
        source.date_in_raw,
        source.time_in_raw,
        source.date_out_raw,
        source.time_out_raw,
    )
    return (
        all(not _raw_is_blank(value) for value in raw_values)
        and bool(record.nik)
        and record.date_in is not None
        and record.time_in is not None
        and record.date_out is not None
        and record.time_out is not None
    )


def _remove_complete_duplicates(final_records, source_records, eligible):
    source_by_id = None
    seen = set()
    unique = []
    anomalies = []
    for record in final_records:
        if not eligible.get(record.record_id, False):
            unique.append(record)
            continue
        key = (
            record.nik,
            record.date_in,
            record.time_in,
            record.date_out,
            record.time_out,
        )
        if key not in seen:
            seen.add(key)
            unique.append(record)
            continue
        if source_by_id is None:
            source_by_id = {
                source.record_id: source
                for source in source_records
            }
        anomalies.append(
            RepairAnomaly(
                record_id=record.record_id,
                anomaly_code=str(AnomalyCode.DUPLICATE_RECORD),
                reason=(
                    "Record duplikat dengan NIK, tanggal, Time_In, dan Time_Out "
                    "yang sama; record pertama dipertahankan."
                ),
                action="EXCLUDED_FROM_FINAL_RECORDS",
                source=source_by_id[record.record_id],
            )
        )
    return unique, anomalies


def _raw_is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
