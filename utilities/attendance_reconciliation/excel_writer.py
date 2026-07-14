"""Generate the eight-sheet reconciliation workbook."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from utilities.attendance_reconciliation.matcher import STATUS_GUIDE
from utilities.attendance_reconciliation.models import ALL_COMPARISON_STATUSES
from utilities.attendance_reconciliation.models import ComparisonRecord
from utilities.attendance_reconciliation.models import ConflictRecord
from utilities.attendance_reconciliation.models import ReconciliationRequest
from utilities.attendance_reconciliation.models import ReconciliationScan
from utilities.attendance_reconciliation.models import SourceAuditRecord
from utilities.attendance_reconciliation.models import STATUS_INVALID_SOURCE_DATA
from utilities.attendance_reconciliation.models import check_cancelled
from utilities.attendance_reconciliation.normalizer import format_date
from utilities.attendance_reconciliation.normalizer import format_time


SHEET_ORDER = (
    "Guide_Status",
    "Dashboard",
    "Comparison_Detail",
    "Machine_Anomaly",
    "Revision_Only",
    "Conflict_Review",
    "Duplicate_Source",
    "Scan_Log",
)

HEADER_FILL = "1F4E78"
STATUS_COLORS = {
    "normal": "E2F0D9",
    "attention": "FFF2CC",
    "anomaly": "FCE4D6",
    "revision": "DDEBF7",
    "conflict": "F4CCCC",
    "neutral": "E7E6E6",
}


def status_color(status: str) -> str:
    if status in {
        "MACHINE_COMPLETE_NO_REVISION",
        "MACHINE_COMPLETE_REVISION_MATCH",
    }:
        return STATUS_COLORS["normal"]
    if status == "MACHINE_COMPLETE_REVISION_DIFFERENT":
        return STATUS_COLORS["attention"]
    if status.startswith("MACHINE_ANOMALY"):
        return STATUS_COLORS["anomaly"]
    if status == "REVISION_ONLY":
        return STATUS_COLORS["revision"]
    if "CONFLICT" in status or "INVALID" in status or "CROSS_DATE" in status:
        return STATUS_COLORS["conflict"]
    return STATUS_COLORS["neutral"]


class ReconciliationExcelWriter:
    def write(
        self,
        path: Path,
        job_id: str,
        request: ReconciliationRequest,
        scan: ReconciliationScan,
        comparisons: list[ComparisonRecord],
        conflicts: list[ConflictRecord],
        duplicates: list[SourceAuditRecord],
        summary: dict[str, Any],
        cancel_event: Event | None = None,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.xlsx")
        workbook = Workbook()
        workbook.active.title = SHEET_ORDER[0]
        for name in SHEET_ORDER[1:]:
            workbook.create_sheet(name)
        try:
            self._guide(workbook["Guide_Status"], job_id, request)
            check_cancelled(cancel_event)
            self._dashboard(workbook["Dashboard"], summary)
            check_cancelled(cancel_event)
            self._comparison(workbook["Comparison_Detail"], comparisons)
            check_cancelled(cancel_event)
            self._machine_anomaly(
                workbook["Machine_Anomaly"], scan, comparisons
            )
            check_cancelled(cancel_event)
            self._revision_only(workbook["Revision_Only"], comparisons)
            self._conflicts(workbook["Conflict_Review"], conflicts)
            self._duplicates(workbook["Duplicate_Source"], duplicates)
            self._scan_log(workbook["Scan_Log"], scan)
            for sheet in workbook.worksheets:
                self._style_table(sheet)
            check_cancelled(cancel_event)
            workbook.save(temporary)
            temporary.replace(path)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
        finally:
            workbook.close()
        return path

    def _guide(self, sheet: Any, job_id: str, request: ReconciliationRequest) -> None:
        identity = [
            ("Report Name", "Comparison-Attendance Reconciliation"),
            ("Comparison Job ID", job_id),
            ("Workflow", request.workflow),
            ("Start Date", format_date(request.start_date)),
            ("End Date", format_date(request.end_date)),
            ("Attendance Source Root", str(request.attendance_path)),
            ("Outlook-Revisi Source Root", str(request.outlook_path)),
            ("Generated At", f"{datetime.now():%Y-%m-%d %H:%M:%S}"),
            ("Engine Version", "1.0.0"),
        ]
        sheet.append(["Identity", "Value"])
        for row in identity:
            sheet.append(row)
        sheet.append([])
        sheet.append(["Prinsip Utama"])
        sheet.append(["Attendance merupakan sumber data utama dan paling valid."])
        sheet.append(["Outlook hanya data revisi pendukung."])
        sheet.append(["Report hanya menjelaskan hasil perbandingan."])
        sheet.append(["Report tidak mengubah data Attendance asli."])
        sheet.append([])
        sheet.append([
            "Status Code", "Kategori", "Penjelasan Bahasa Indonesia",
            "Tindakan", "Warna",
        ])
        for status in ALL_COMPARISON_STATUSES:
            if status == STATUS_INVALID_SOURCE_DATA:
                category, description, review = (
                    "Konflik",
                    "Data sumber tidak dapat dinormalisasi atau tidak valid.",
                    True,
                )
            else:
                category, description, review = STATUS_GUIDE[status]
            row = [
                status,
                category,
                description,
                "Review manual" if review else "Tidak perlu tindakan",
                status_color(status),
            ]
            sheet.append(row)
            for cell in sheet[sheet.max_row]:
                cell.fill = PatternFill("solid", fgColor=status_color(status))

    def _dashboard(self, sheet: Any, summary: dict[str, Any]) -> None:
        sheet.append(["Metric", "Value"])
        labels = [
            ("Workflow", "workflow"),
            ("Selected Start Date", "start_date"),
            ("Selected End Date", "end_date"),
            ("Attendance Reports Found", "attendance_reports_found"),
            ("Attendance Reports Used", "attendance_reports_used"),
            ("Attendance Reports Skipped", "attendance_reports_skipped"),
            ("Outlook Reports Found", "outlook_reports_found"),
            ("Outlook Reports Used", "outlook_reports_used"),
            ("Outlook Reports Skipped", "outlook_reports_skipped"),
            ("Attendance Records", "attendance_records"),
            ("Machine Complete", "machine_complete"),
            ("Machine Anomalies", "machine_anomalies"),
            ("Outlook Valid Revisions", "outlook_valid_revisions"),
            ("Revision Only", "revision_only"),
            ("Machine Source Conflict", "machine_source_conflict"),
            ("Multiple Revision Conflict", "multiple_revision_conflict"),
            ("Invalid Source Data", "invalid_source_data"),
            ("Total Comparison Records", "total_comparison_records"),
            ("Warnings", "warnings"),
        ]
        for label, key in labels:
            value = summary.get(key, "")
            if isinstance(value, list):
                value = "\n".join(value)
            sheet.append([label, value])

    def _comparison(
        self, sheet: Any, comparisons: list[ComparisonRecord]
    ) -> None:
        headers = [
            "No", "Workflow", "NIK", "Nama", "Tanggal", "Machine In",
            "Machine Out", "Machine Tap Count", "Machine Pair Status",
            "Machine Validation Status", "Machine Remarks", "Source MDB",
            "Attendance Source Report", "Attendance Source Count",
            "Original Anomaly Time", "Original Anomaly Column",
            "Interpreted Machine In", "Interpreted Machine Out",
            "Interpretation Rule", "Revision In", "Revision Out",
            "Revision Status", "Attachment Name", "Outlook Source Report",
            "Outlook Source Row", "Revision Duplicate Count",
            "Comparison Status", "Status Description", "Category",
            "Review Required", "Review Note",
        ]
        sheet.append(headers)
        for number, item in enumerate(comparisons, 1):
            machine = item.machine
            revision = item.revision
            sheet.append([
                number,
                item.key.workflow,
                item.key.nik,
                machine.name if machine else "",
                format_date(item.key.attendance_date),
                format_time(machine.machine_in) if machine else "",
                format_time(machine.machine_out) if machine else "",
                machine.tap_count if machine else "",
                machine.pair_status if machine else "",
                machine.validation_status if machine else "",
                machine.remarks if machine else "",
                machine.source_mdb if machine else "",
                "\n".join(str(path) for path in machine.source_reports)
                if machine else "",
                machine.source_count if machine else 0,
                format_time(machine.original_anomaly_time) if machine else "",
                machine.original_anomaly_column if machine else "",
                format_time(machine.interpreted_machine_in) if machine else "",
                format_time(machine.interpreted_machine_out) if machine else "",
                machine.interpretation_rule if machine else "",
                format_time(revision.revision_in) if revision else "",
                format_time(revision.revision_out) if revision else "",
                "COMPLETE" if revision and revision.complete else (
                    "INCOMPLETE" if revision else "NOT_AVAILABLE"
                ),
                "\n".join(revision.attachments) if revision else "",
                "\n".join(str(path) for path in revision.source_reports)
                if revision else "",
                ", ".join(str(row) for row in revision.source_rows)
                if revision else "",
                revision.duplicate_count if revision else 0,
                item.status,
                item.status_description,
                item.category,
                "YES" if item.review_required else "NO",
                item.review_note,
            ])
            for cell in sheet[sheet.max_row]:
                cell.fill = PatternFill("solid", fgColor=status_color(item.status))

    def _machine_anomaly(
        self,
        sheet: Any,
        scan: ReconciliationScan,
        comparisons: list[ComparisonRecord],
    ) -> None:
        sheet.append([
            "No", "Workflow", "NIK", "Nama", "Tanggal", "Original In",
            "Original Out", "Tap Count", "Pair Status", "Validation Status",
            "Remarks", "Original Anomaly Time", "Original Anomaly Column",
            "Interpreted Machine In", "Interpreted Machine Out",
            "Interpretation Rule", "Internal Status", "Revision Status",
            "Comparison Status", "Source Report", "Source Row", "Review Note",
        ])
        status_by_key = {item.key: item for item in comparisons}
        anomalies = [item for item in scan.attendance.records if item.is_anomaly]
        for number, record in enumerate(anomalies, 1):
            comparison = status_by_key.get(record.key)
            sheet.append([
                number, record.workflow, record.nik, record.name,
                format_date(record.attendance_date),
                format_time(record.machine_in), format_time(record.machine_out),
                record.tap_count, record.pair_status, record.validation_status,
                record.remarks, format_time(record.original_anomaly_time),
                record.original_anomaly_column,
                format_time(record.interpreted_machine_in),
                format_time(record.interpreted_machine_out),
                record.interpretation_rule, record.internal_status,
                "AVAILABLE" if comparison and comparison.revision else "NOT_AVAILABLE",
                comparison.status if comparison else STATUS_INVALID_SOURCE_DATA,
                str(record.source_report), record.source_row,
                comparison.review_note if comparison else "Review manual diperlukan.",
            ])
        number = len(anomalies)
        for invalid in scan.attendance.invalid_records:
            if invalid.source_sheet != "Anomaly":
                continue
            number += 1
            sheet.append([
                number,
                invalid.workflow,
                invalid.nik,
                "",
                invalid.raw_date,
                "",
                "",
                "",
                "",
                "INVALID",
                invalid.reason,
                "",
                "",
                "",
                "",
                "",
                "INVALID_SINGLE_TAP_TIME"
                if "SINGLE_TAP" in invalid.reason
                else STATUS_INVALID_SOURCE_DATA,
                "NOT_AVAILABLE",
                STATUS_INVALID_SOURCE_DATA,
                str(invalid.source_report),
                invalid.source_row,
                "Review manual diperlukan.",
            ])

    def _revision_only(
        self, sheet: Any, comparisons: list[ComparisonRecord]
    ) -> None:
        sheet.append([
            "No", "Workflow", "NIK", "Tanggal", "Revision In",
            "Revision Out", "Attachment Name", "Outlook Source Report",
            "Outlook Source Row", "Status", "Description", "Review Note",
        ])
        rows = [item for item in comparisons if item.status == "REVISION_ONLY"]
        for number, item in enumerate(rows, 1):
            revision = item.revision
            sheet.append([
                number, item.key.workflow, item.key.nik,
                format_date(item.key.attendance_date),
                format_time(revision.revision_in) if revision else "",
                format_time(revision.revision_out) if revision else "",
                "\n".join(revision.attachments) if revision else "",
                "\n".join(str(path) for path in revision.source_reports)
                if revision else "",
                ", ".join(str(row) for row in revision.source_rows)
                if revision else "",
                item.status,
                "Data mesin tidak ditemukan dalam report dan periode yang dipilih.",
                item.review_note,
            ])

    def _conflicts(self, sheet: Any, conflicts: list[ConflictRecord]) -> None:
        sheet.append([
            "No", "Conflict Type", "Record Key", "Source Type",
            "Source Report", "Source Row", "Values", "Reason",
            "Review Required",
        ])
        for number, item in enumerate(conflicts, 1):
            sheet.append([
                number, item.conflict_type,
                item.key.display() if item.key else "",
                item.source_type, item.source_report, item.source_row,
                item.values, item.reason, "YES",
            ])

    def _duplicates(
        self, sheet: Any, duplicates: list[SourceAuditRecord]
    ) -> None:
        sheet.append([
            "No", "Duplicate Type", "Record Key", "Source Count",
            "Sources", "Values",
        ])
        for number, item in enumerate(duplicates, 1):
            sheet.append([
                number, item.duplicate_type, item.key.display(),
                item.source_count, "\n".join(item.sources), "\n".join(item.values),
            ])

    def _scan_log(self, sheet: Any, scan: ReconciliationScan) -> None:
        sheet.append([
            "No", "Source Type", "File Path", "Workflow Detected", "Status",
            "Reason", "Records Read", "Period Min", "Period Max", "Timestamp",
        ])
        entries = [*scan.attendance.log_entries, *scan.outlook.log_entries]
        for number, item in enumerate(entries, 1):
            sheet.append([
                number, item.source_type, str(item.file_path),
                item.workflow_detected, item.status, item.reason,
                item.records_read, format_date(item.period_min),
                format_date(item.period_max),
                f"{item.timestamp:%Y-%m-%d %H:%M:%S}",
            ])

    def _style_table(self, sheet: Any) -> None:
        thin = Side(style="thin", color="D9D9D9")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_rows = {1}
        if sheet.title == "Guide_Status":
            header_rows.add(18)
        for row in sheet.iter_rows():
            for cell in row:
                cell.border = border
                cell.alignment = Alignment(
                    vertical="top", wrap_text=True
                )
                if cell.row in header_rows:
                    cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
                    cell.font = Font(bold=True, color="FFFFFF")
        sheet.freeze_panes = "A2"
        if sheet.max_row >= 1 and sheet.max_column >= 1:
            sheet.auto_filter.ref = sheet.dimensions
        for column in range(1, sheet.max_column + 1):
            values = [
                len(str(sheet.cell(row, column).value or ""))
                for row in range(1, min(sheet.max_row, 100) + 1)
            ]
            width = min(max(values, default=8) + 2, 45)
            sheet.column_dimensions[get_column_letter(column)].width = max(10, width)
