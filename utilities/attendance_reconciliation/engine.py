"""Orchestrate scan, reconciliation, and artifact generation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from threading import Event

from utilities.attendance_reconciliation.attendance_reader import (
    AttendanceReportReader,
)
from utilities.attendance_reconciliation.duplicate_detector import (
    detect_machine_duplicates,
)
from utilities.attendance_reconciliation.duplicate_detector import (
    detect_revision_duplicates,
)
from utilities.attendance_reconciliation.excel_writer import (
    ReconciliationExcelWriter,
)
from utilities.attendance_reconciliation.matcher import invalid_conflicts
from utilities.attendance_reconciliation.matcher import match_records
from utilities.attendance_reconciliation.models import ENGINE_VERSION
from utilities.attendance_reconciliation.models import ReconciliationCancelled
from utilities.attendance_reconciliation.models import ReconciliationRequest
from utilities.attendance_reconciliation.models import ReconciliationResult
from utilities.attendance_reconciliation.models import ReconciliationScan
from utilities.attendance_reconciliation.models import check_cancelled
from utilities.attendance_reconciliation.normalizer import format_date
from utilities.attendance_reconciliation.outlook_reader import OutlookReportReader
from utilities.attendance_reconciliation.process_logger import (
    ReconciliationProcessLogger,
)
from utilities.attendance_reconciliation.summary_writer import write_summary
from utilities.attendance_reconciliation.validators import validate_request


class ReconciliationEngine:
    def __init__(self) -> None:
        self.attendance_reader = AttendanceReportReader()
        self.outlook_reader = OutlookReportReader()
        self.excel_writer = ReconciliationExcelWriter()

    def scan(
        self,
        request: ReconciliationRequest,
        cancel_event: Event | None = None,
    ) -> ReconciliationScan:
        validate_request(request)
        check_cancelled(cancel_event)
        attendance = self.attendance_reader.read_folder(
            request.attendance_path,
            request.workflow,
            request.start_date,
            request.end_date,
            cancel_event,
        )
        check_cancelled(cancel_event)
        outlook = self.outlook_reader.read_folder(
            request.outlook_path,
            request.workflow,
            request.start_date,
            request.end_date,
            cancel_event,
        )
        if attendance.reports_used == 0:
            raise ValueError(
                "No usable Attendance report was found for the selected "
                "workflow and period."
            )
        warnings = [
            item.reason
            for item in [*attendance.log_entries, *outlook.log_entries]
            if item.status != "USED" and item.reason
        ]
        if outlook.reports_used == 0:
            warnings.append(
                "No usable Outlook-Revisi report was found; machine records "
                "will be compared without revisions."
            )
        if outlook.audit_anomalies:
            warnings.append(
                f"{len(outlook.audit_anomalies)} Outlook Data_Anomaly row(s) "
                "were retained for audit only."
            )
        return ReconciliationScan(
            attendance=attendance,
            outlook=outlook,
            fingerprint=request.fingerprint(),
            warnings=list(dict.fromkeys(warnings)),
        )

    def run(
        self,
        request: ReconciliationRequest,
        scan: ReconciliationScan | None = None,
        cancel_event: Event | None = None,
    ) -> ReconciliationResult:
        validate_request(request)
        if scan is None:
            scan = self.scan(request, cancel_event)
        if scan.fingerprint != request.fingerprint():
            raise ValueError("Scan result is stale. Scan Reports again.")

        job_id, job_folder = self._reserve_job_folder(
            request.output_folder, request.workflow
        )
        process_log = job_folder / "Process.log"
        summary_json = job_folder / "summary.json"
        report_file = (
            job_folder / "Report"
            / f"Comparison_Attendance_Reconciliation_{request.workflow}_{job_id}.xlsx"
        )
        report_file.parent.mkdir(exist_ok=False)
        process = ReconciliationProcessLogger(process_log)
        process.write(f"Job started: {job_id}")
        process.write(f"Workflow: {request.workflow}")
        process.write(
            f"Selected period: {format_date(request.start_date)} - "
            f"{format_date(request.end_date)}"
        )
        process.write(f"Attendance source: {request.attendance_path}")
        process.write(f"Outlook-Revisi source: {request.outlook_path}")

        try:
            check_cancelled(cancel_event)
            machines = detect_machine_duplicates(list(scan.attendance.records))
            revisions = detect_revision_duplicates(list(scan.outlook.records))
            comparisons, conflicts = match_records(machines, revisions)
            conflicts.extend(
                invalid_conflicts(
                    [
                        *scan.attendance.invalid_records,
                        *scan.outlook.invalid_records,
                        *scan.outlook.audit_anomalies,
                    ]
                )
            )
            duplicates = [*machines.audits, *revisions.audits]
            process.write(
                f"Report discovery: Attendance found={scan.attendance.reports_found}, "
                f"used={scan.attendance.reports_used}; Outlook found="
                f"{scan.outlook.reports_found}, used={scan.outlook.reports_used}."
            )
            for entry in [
                *scan.attendance.log_entries,
                *scan.outlook.log_entries,
            ]:
                if entry.status != "USED":
                    process.write(
                        f"Skipped source [{entry.status}]: {entry.file_path.name}; "
                        f"reason={entry.reason or 'not usable'}."
                    )
            process.write(
                f"Records read: Attendance={len(scan.attendance.records)}, "
                f"Outlook valid revisions={len(scan.outlook.records)}."
            )
            for warning in scan.warnings:
                process.write(f"Warning: {warning}")
            process.write(
                f"Duplicate results: machine={len(machines.audits)}, "
                f"revision={len(revisions.audits)}."
            )
            summary = self._summary(
                request, scan, job_id, job_folder, comparisons, conflicts,
                duplicates,
            )
            check_cancelled(cancel_event)
            self.excel_writer.write(
                report_file,
                job_id,
                request,
                scan,
                comparisons,
                conflicts,
                duplicates,
                summary,
                cancel_event,
            )
            write_summary(summary_json, summary)
            process.write(
                f"Comparison summary: total={len(comparisons)}, "
                f"review={sum(item.review_required for item in comparisons)}."
            )
            process.write(f"Report created: {report_file}")
            process.write(f"Summary created: {summary_json}")
            process.write("Job completed successfully.")
            return ReconciliationResult(
                True, job_id, job_folder, report_file, process_log,
                summary_json, scan, comparisons, conflicts, duplicates,
                scan.warnings,
            )
        except ReconciliationCancelled:
            process.write("CANCELLED: process stopped safely by user request.")
            raise
        except Exception as error:
            process.write(f"FAILED: {error}")
            raise

    def _summary(
        self,
        request,
        scan,
        job_id,
        job_folder,
        comparisons,
        conflicts,
        duplicates,
    ) -> dict[str, object]:
        statuses = Counter(item.status for item in comparisons)
        machine_records = list(scan.attendance.records)
        return {
            "job_id": job_id,
            "engine_version": ENGINE_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "workflow": request.workflow,
            "start_date": format_date(request.start_date),
            "end_date": format_date(request.end_date),
            "source_mode": request.source_mode,
            "attendance_root": str(request.attendance_path),
            "outlook_root": str(request.outlook_path),
            "output_folder": str(job_folder),
            "attendance_reports_found": scan.attendance.reports_found,
            "attendance_reports_used": scan.attendance.reports_used,
            "attendance_reports_skipped": scan.attendance.reports_skipped,
            "outlook_reports_found": scan.outlook.reports_found,
            "outlook_reports_used": scan.outlook.reports_used,
            "outlook_reports_skipped": scan.outlook.reports_skipped,
            "attendance_records": len(machine_records),
            "machine_complete": sum(not item.is_anomaly for item in machine_records),
            "machine_anomalies": sum(item.is_anomaly for item in machine_records),
            "outlook_valid_revisions": len(scan.outlook.records),
            "revision_only": statuses["REVISION_ONLY"],
            "machine_source_conflict": statuses["MACHINE_SOURCE_CONFLICT"],
            "multiple_revision_conflict": statuses[
                "MULTIPLE_REVISION_CONFLICT"
            ],
            "invalid_source_data": len(scan.attendance.invalid_records)
            + len(scan.outlook.invalid_records)
            + len(scan.outlook.audit_anomalies),
            "duplicate_machine": sum(
                item.duplicate_type == "MACHINE_EXACT_DUPLICATE"
                for item in duplicates
            ),
            "duplicate_revision": sum(
                item.duplicate_type == "REVISION_EXACT_DUPLICATE"
                for item in duplicates
            ),
            "total_comparison_records": len(comparisons),
            "warnings": scan.warnings,
            "success": True,
            "error_message": "",
        }

    @staticmethod
    def _reserve_job_folder(output_root: Path, workflow: str) -> tuple[str, Path]:
        root = output_root / "Utilities" / "Attendance-Reconciliation" / workflow
        base = datetime.now().strftime("%Y%m%d_%H%M%S")
        for sequence in range(1, 1000):
            job_id = base if sequence == 1 else f"{base}_{sequence:02d}"
            folder = root / job_id
            try:
                folder.mkdir(parents=True, exist_ok=False)
                return job_id, folder
            except FileExistsError:
                continue
        raise RuntimeError(f"Unable to reserve reconciliation job folder: {root}")
