"""Data models for Attendance and Outlook reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from threading import Event


ENGINE_VERSION = "1.0.0"

SOURCE_MODE_SCAN = "Scan Entire Output Folder"
SOURCE_MODE_JOB = "Select Specific Job Folder"

STATUS_MACHINE_COMPLETE_NO_REVISION = "MACHINE_COMPLETE_NO_REVISION"
STATUS_MACHINE_COMPLETE_REVISION_MATCH = "MACHINE_COMPLETE_REVISION_MATCH"
STATUS_MACHINE_COMPLETE_REVISION_DIFFERENT = "MACHINE_COMPLETE_REVISION_DIFFERENT"
STATUS_MACHINE_ANOMALY_NO_REVISION = "MACHINE_ANOMALY_NO_REVISION"
STATUS_MACHINE_ANOMALY_REVISION_AVAILABLE = "MACHINE_ANOMALY_REVISION_AVAILABLE"
STATUS_MACHINE_ANOMALY_REVISION_INCOMPLETE = "MACHINE_ANOMALY_REVISION_INCOMPLETE"
STATUS_REVISION_ONLY = "REVISION_ONLY"
STATUS_MACHINE_SOURCE_CONFLICT = "MACHINE_SOURCE_CONFLICT"
STATUS_MULTIPLE_REVISION_CONFLICT = "MULTIPLE_REVISION_CONFLICT"
STATUS_INVALID_SOURCE_DATA = "INVALID_SOURCE_DATA"

ALL_COMPARISON_STATUSES = (
    STATUS_MACHINE_COMPLETE_NO_REVISION,
    STATUS_MACHINE_COMPLETE_REVISION_MATCH,
    STATUS_MACHINE_COMPLETE_REVISION_DIFFERENT,
    STATUS_MACHINE_ANOMALY_NO_REVISION,
    STATUS_MACHINE_ANOMALY_REVISION_AVAILABLE,
    STATUS_MACHINE_ANOMALY_REVISION_INCOMPLETE,
    STATUS_REVISION_ONLY,
    STATUS_MACHINE_SOURCE_CONFLICT,
    STATUS_MULTIPLE_REVISION_CONFLICT,
    STATUS_INVALID_SOURCE_DATA,
)


class ReconciliationCancelled(RuntimeError):
    """Raised when a cooperative cancellation request is observed."""


@dataclass(frozen=True, slots=True, order=True)
class RecordKey:
    workflow: str
    nik: str
    attendance_date: date

    def display(self) -> str:
        return f"{self.workflow}|{self.nik}|{self.attendance_date:%m/%d/%Y}"


@dataclass(slots=True)
class MachineRecord:
    workflow: str
    nik: str
    name: str
    attendance_date: date
    machine_in: time | None
    machine_out: time | None
    tap_count: int
    pair_status: str
    validation_status: str
    remarks: str
    source_mdb: str
    source_report: Path
    source_row: int
    is_anomaly: bool = False
    original_anomaly_time: time | None = None
    original_anomaly_column: str = ""
    interpreted_machine_in: time | None = None
    interpreted_machine_out: time | None = None
    interpretation_rule: str = ""
    internal_status: str = ""
    source_reports: list[Path] = field(default_factory=list)
    source_count: int = 1

    @property
    def key(self) -> RecordKey:
        return RecordKey(self.workflow, self.nik, self.attendance_date)

    @property
    def values(self) -> tuple[time | None, time | None, bool]:
        return self.machine_in, self.machine_out, self.is_anomaly


@dataclass(slots=True)
class RevisionRecord:
    workflow: str
    nik: str
    attendance_date: date
    revision_in: time | None
    revision_out: time | None
    attachment_name: str
    source_report: Path
    source_row: int
    date_in: date | None = None
    date_out: date | None = None
    duplicate_count: int = 1
    source_reports: list[Path] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)

    @property
    def key(self) -> RecordKey:
        return RecordKey(self.workflow, self.nik, self.attendance_date)

    @property
    def values(self) -> tuple[time | None, time | None]:
        return self.revision_in, self.revision_out

    @property
    def complete(self) -> bool:
        return self.revision_in is not None and self.revision_out is not None


@dataclass(slots=True)
class InvalidSourceRecord:
    source_type: str
    source_report: Path
    source_sheet: str
    source_row: int
    workflow: str
    nik: str
    raw_date: str
    reason: str
    code: str = STATUS_INVALID_SOURCE_DATA


@dataclass(slots=True)
class SourceAuditRecord:
    duplicate_type: str
    key: RecordKey
    source_count: int
    sources: list[str]
    values: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScanLogEntry:
    source_type: str
    file_path: Path
    workflow_detected: str
    status: str
    reason: str = ""
    records_read: int = 0
    period_min: date | None = None
    period_max: date | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class SourceScanResult:
    source_type: str
    records: list[MachineRecord] | list[RevisionRecord] = field(
        default_factory=list
    )
    invalid_records: list[InvalidSourceRecord] = field(default_factory=list)
    audit_anomalies: list[InvalidSourceRecord] = field(default_factory=list)
    log_entries: list[ScanLogEntry] = field(default_factory=list)

    @property
    def reports_found(self) -> int:
        return len(self.log_entries)

    @property
    def reports_used(self) -> int:
        return sum(item.status == "USED" for item in self.log_entries)

    @property
    def reports_skipped(self) -> int:
        return self.reports_found - self.reports_used


@dataclass(slots=True)
class ReconciliationScan:
    attendance: SourceScanResult
    outlook: SourceScanResult
    fingerprint: tuple[str, ...]
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ComparisonRecord:
    key: RecordKey
    status: str
    status_description: str
    category: str
    review_required: bool
    review_note: str = ""
    machine: MachineRecord | None = None
    revision: RevisionRecord | None = None


@dataclass(slots=True)
class ConflictRecord:
    conflict_type: str
    key: RecordKey | None
    source_type: str
    source_report: str
    source_row: int | str
    values: str
    reason: str


@dataclass(slots=True)
class ReconciliationRequest:
    source_mode: str
    workflow: str
    attendance_path: Path
    outlook_path: Path
    start_date: date
    end_date: date
    output_folder: Path

    def fingerprint(self) -> tuple[str, ...]:
        return (
            self.source_mode,
            self.workflow,
            str(self.attendance_path.resolve()),
            str(self.outlook_path.resolve()),
            self.start_date.isoformat(),
            self.end_date.isoformat(),
            str(self.output_folder.resolve()),
        )


@dataclass(slots=True)
class ReconciliationResult:
    success: bool
    job_id: str
    output_folder: Path
    report_file: Path | None
    process_log: Path
    summary_json: Path
    scan: ReconciliationScan
    comparisons: list[ComparisonRecord]
    conflicts: list[ConflictRecord]
    duplicates: list[SourceAuditRecord]
    warnings: list[str]
    error_message: str = ""
    cancelled: bool = False


def check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ReconciliationCancelled("Reconciliation process cancelled.")
