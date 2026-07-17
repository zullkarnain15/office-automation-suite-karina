"""Orchestration engine for Excel/TXT Attachment Consolidation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event

from outlook.parser import OutlookAttachmentParser
from outlook.parser import OutlookTxtWriter
from shared.config_manager import OutlookRevisiConfigurationReader
from utilities.attachment_consolidation.config_resolver import (
    resolve_outlook_configuration,
)
from utilities.attachment_consolidation.excel_reader import (
    ConsolidationExcelReader,
)
from utilities.attachment_consolidation.job_manager import ConsolidationJobManager
from utilities.attachment_consolidation.models import (
    MODE_EXCEL,
    ConsolidationCancelled,
    ConsolidationFileResult,
    ConsolidationRequest,
    ConsolidationResult,
    ConsolidationScan,
    ProgressCallback,
    check_cancelled,
)
from utilities.attachment_consolidation.process_logger import (
    ConsolidationProcessLogger,
)
from utilities.attachment_consolidation.report_writer import (
    ConsolidationReportWriter,
)
from utilities.attachment_consolidation.scanner import AttachmentScanner
from utilities.attachment_consolidation.statuses import (
    FILE_CANCELLED,
    FILE_FAILED,
    FILE_NO_VALID,
    FILE_PARTIAL,
    FILE_SUCCESS,
)
from utilities.attachment_consolidation.summary_writer import write_summary
from utilities.attachment_consolidation.txt_reader import ConsolidationTXTReader


class AttachmentConsolidationEngine:
    def __init__(
        self,
        scanner: AttachmentScanner | None = None,
        parser: OutlookAttachmentParser | None = None,
        writer: OutlookTxtWriter | None = None,
        report_writer: ConsolidationReportWriter | None = None,
        job_manager: ConsolidationJobManager | None = None,
    ) -> None:
        shared_parser = parser or OutlookAttachmentParser()
        self.scanner = scanner or AttachmentScanner()
        self.excel_reader = ConsolidationExcelReader(shared_parser)
        self.txt_reader = ConsolidationTXTReader(shared_parser)
        self.writer = writer or OutlookTxtWriter()
        self.report_writer = report_writer or ConsolidationReportWriter()
        self.job_manager = job_manager or ConsolidationJobManager()

    def scan(
        self,
        request: ConsolidationRequest,
        cancel_event: Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> ConsolidationScan:
        self._progress(progress, "scan", 0, 1, "Memindai Source Root...")
        result = self.scanner.scan(request, cancel_event)
        self._progress(
            progress,
            "scan",
            1,
            1,
            f"Scan selesai: {len(result.files)} file ditemukan.",
        )
        return result

    def run(
        self,
        request: ConsolidationRequest,
        scan: ConsolidationScan | None = None,
        cancel_event: Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> ConsolidationResult:
        self.scanner.validate_request(request)
        current_scan = scan or self.scan(request, cancel_event, progress)
        if current_scan.request_fingerprint != request.fingerprint():
            raise ValueError("Input berubah. Jalankan Scan Files kembali.")
        if not current_scan.processable_files:
            raise ValueError("Tidak ada file yang dapat diproses.")

        configuration_file = resolve_outlook_configuration(
            request.configuration_file
        )
        configuration = OutlookRevisiConfigurationReader(
            configuration_file
        ).read()
        max_lines = self._max_lines(configuration.general.get("TXT_Max_Lines"))

        started_at = datetime.now()
        artifacts = self.job_manager.reserve(
            request.output_root,
            request.workflow,
            now=started_at,
        )
        process = ConsolidationProcessLogger(artifacts.process_log)
        process.write(
            f"Job dimulai. Mode={request.mode}; Workflow={request.workflow}"
        )
        process.write(f"Source Root: {request.source_root}")
        process.write(f"Configuration: {configuration_file}")
        process.write(f"TXT_Max_Lines: {max_lines}")

        file_results = [
            ConsolidationFileResult(
                scanned=item,
                status=item.status,
                message=item.reason,
            )
            for item in current_scan.files
            if not item.processable
        ]
        records = []
        anomalies = []
        output_files: list[Path] = []
        error_message = ""
        cancelled = False
        success = False

        try:
            candidates = current_scan.processable_files
            total = len(candidates)
            reader = (
                self.excel_reader
                if request.mode == MODE_EXCEL
                else self.txt_reader
            )
            for index, scanned_file in enumerate(candidates, 1):
                check_cancelled(cancel_event)
                self._progress(
                    progress,
                    "process",
                    index - 1,
                    total,
                    f"Membaca {scanned_file.relative_path}",
                )
                parse_result = reader.read(scanned_file.path)
                records.extend(parse_result.records)
                anomalies.extend(parse_result.anomalies)
                file_status = self._file_status(parse_result)
                file_result = ConsolidationFileResult(
                    scanned=scanned_file,
                    status=file_status,
                    row_read=parse_result.row_read,
                    valid_count=len(parse_result.records),
                    invalid_count=len(parse_result.anomalies),
                    empty_row_dropped=parse_result.empty_row_dropped,
                    message="\n".join(parse_result.errors),
                )
                file_results.append(file_result)
                process.write(
                    f"{scanned_file.relative_path}: {file_status}; "
                    f"valid={file_result.valid_count}; "
                    f"invalid={file_result.invalid_count}"
                )
                self._progress(
                    progress,
                    "process",
                    index,
                    total,
                    f"Selesai membaca {scanned_file.relative_path}",
                )

            check_cancelled(cancel_event)
            if not records:
                raise ValueError(
                    "Tidak ada record valid. TXT HRIS tidak dibuat."
                )
            self._progress(
                progress,
                "write",
                0,
                1,
                "Menulis TXT HRIS...",
            )
            output_files = self.writer.write(
                records=records,
                output_folder=artifacts.txt_folder,
                workflow=request.workflow,
                max_lines=max_lines,
                job_id=artifacts.job_id,
            )
            self._assign_output_files(file_results, records)
            self._progress(
                progress,
                "write",
                1,
                1,
                f"{len(output_files)} TXT berhasil dibuat.",
            )
            success = True
            process.write(
                f"TXT selesai. Record={len(records)}; File={len(output_files)}"
            )
        except ConsolidationCancelled as error:
            cancelled = True
            error_message = str(error)
            process.write(error_message)
            for item in file_results:
                if item.status == "READY":
                    item.status = FILE_CANCELLED
        except Exception as error:
            error_message = str(error)
            process.write(f"FAILED: {error_message}")

        represented_paths = {
            item.scanned.path.resolve()
            for item in file_results
        }
        for scanned_file in current_scan.processable_files:
            if scanned_file.path.resolve() in represented_paths:
                continue
            file_results.append(
                ConsolidationFileResult(
                    scanned=scanned_file,
                    status=FILE_CANCELLED if cancelled else FILE_FAILED,
                    message=(
                        "Tidak diproses karena pembatalan."
                        if cancelled
                        else "Tidak diproses karena job berhenti lebih awal."
                    ),
                )
            )

        finished_at = datetime.now()
        file_results.sort(
            key=lambda item: item.scanned.relative_path.casefold()
        )
        result = ConsolidationResult(
            success=success,
            request=request,
            scan=current_scan,
            artifacts=artifacts,
            file_results=file_results,
            records=records,
            anomalies=anomalies,
            output_files=output_files,
            max_lines=max_lines,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
            cancelled=cancelled,
        )
        self._write_artifacts(result, process)
        self._progress(
            progress,
            "complete",
            1,
            1,
            "Attachment Consolidation selesai."
            if success
            else error_message,
        )
        return result

    def _write_artifacts(
        self,
        result: ConsolidationResult,
        process: ConsolidationProcessLogger,
    ) -> None:
        self.report_writer.write(result)
        summary = {
            "job_id": result.artifacts.job_id,
            "module": "Attachment Consolidation",
            "mode": result.request.mode,
            "workflow": result.request.workflow,
            "status": (
                "CANCELLED"
                if result.cancelled
                else "SUCCESS"
                if result.success
                else "FAILED"
            ),
            "started_at": result.started_at.isoformat(timespec="seconds"),
            "finished_at": result.finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round(result.duration_seconds, 3),
            "source_root": str(result.request.source_root),
            "output_folder": str(result.artifacts.job_folder),
            "files_found": len(result.scan.files),
            "files_processable": len(result.scan.processable_files),
            "valid_records": len(result.records),
            "invalid_records": len(result.anomalies),
            "txt_max_lines": result.max_lines,
            "txt_files": [str(path) for path in result.output_files],
            "report_file": str(result.artifacts.report_file),
            "error_message": result.error_message,
        }
        write_summary(result.artifacts.summary_json, summary)
        process.write(
            "Job selesai dengan status "
            + summary["status"]
            + f"; durasi={result.duration_seconds:.2f} detik"
        )

    @staticmethod
    def _max_lines(value: object) -> int:
        try:
            max_lines = int(str(value).strip())
        except (TypeError, ValueError) as error:
            raise ValueError(
                "TXT_Max_Lines pada Outlook Configuration harus berupa angka."
            ) from error
        if max_lines <= 0:
            raise ValueError(
                "TXT_Max_Lines pada Outlook Configuration harus lebih dari nol."
            )
        return max_lines

    @staticmethod
    def _file_status(parse_result: object) -> str:
        records = getattr(parse_result, "records", [])
        anomalies = getattr(parse_result, "anomalies", [])
        if records and anomalies:
            return FILE_PARTIAL
        if records:
            return FILE_SUCCESS
        if anomalies:
            if any(
                item.code in {
                    "FILE_READ_FAILED",
                    "MISSING_REQUIRED_COLUMN",
                    "ATTACHMENT_STRUCTURE_INVALID",
                }
                for item in anomalies
            ):
                return FILE_FAILED
            return FILE_NO_VALID
        return FILE_NO_VALID

    @staticmethod
    def _assign_output_files(
        file_results: list[ConsolidationFileResult],
        records: list[object],
    ) -> None:
        outputs_by_source: dict[Path, set[Path]] = {}
        for record in records:
            output_file = getattr(record, "output_file", None)
            if output_file is None:
                continue
            source = Path(record.source_file).resolve()
            outputs_by_source.setdefault(source, set()).add(
                Path(output_file)
            )
        for item in file_results:
            item.output_files = sorted(
                outputs_by_source.get(item.scanned.path.resolve(), set()),
                key=str,
            )

    @staticmethod
    def _progress(
        callback: ProgressCallback | None,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if callback is not None:
            callback(stage, current, total, message)
