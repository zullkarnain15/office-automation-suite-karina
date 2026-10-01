"""Typed UI7 Utilities requests, events, validation, and result models."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class UtilitiesFeature(StrEnum):
    COMPARISON_RESULT = "COMPARISON_RESULT"
    ATTACHMENT_CONSOLIDATION = "ATTACHMENT_CONSOLIDATION"
    ATT_DATA_REPAIR = "ATT_DATA_REPAIR"


class UtilitiesFileRole(StrEnum):
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    COMPARISON_REPORT = "COMPARISON_REPORT"
    CONSOLIDATED_TXT = "CONSOLIDATED_TXT"
    CONSOLIDATION_REPORT = "CONSOLIDATION_REPORT"
    PROCESS_LOG = "PROCESS_LOG"
    SUMMARY_JSON = "SUMMARY_JSON"
    REJECTED_FILES_REPORT = "REJECTED_FILES_REPORT"
    SOURCE_ATTENDANCE_REFERENCE = "SOURCE_ATTENDANCE_REFERENCE"
    SOURCE_OUTLOOK_REFERENCE = "SOURCE_OUTLOOK_REFERENCE"
    SOURCE_ATTACHMENT_FOLDER = "SOURCE_ATTACHMENT_FOLDER"
    SOURCE_REPORT = "SOURCE_REPORT"
    HRIS_TXT = "HRIS_TXT"
    EXCEL_REPORT = "EXCEL_REPORT"


class UtilitiesJobPhase(StrEnum):
    JOB_CREATED = "JOB_CREATED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    SOURCE_INSPECTION_STARTED = "SOURCE_INSPECTION_STARTED"
    SOURCE_INSPECTION_COMPLETED = "SOURCE_INSPECTION_COMPLETED"
    SOURCE_SCAN_STARTED = "SOURCE_SCAN_STARTED"
    SOURCE_SCAN_COMPLETED = "SOURCE_SCAN_COMPLETED"
    COMPARISON_STARTED = "COMPARISON_STARTED"
    CONSOLIDATION_STARTED = "CONSOLIDATION_STARTED"
    TXT_WRITING_STARTED = "TXT_WRITING_STARTED"
    REPORT_WRITING_STARTED = "REPORT_WRITING_STARTED"
    OUTPUT_CREATED = "OUTPUT_CREATED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    JOB_CANCELLED = "JOB_CANCELLED"


@dataclass(frozen=True, slots=True)
class UtilitiesFeatureSummary:
    feature: UtilitiesFeature
    title: str
    description: str
    status: str


@dataclass(frozen=True, slots=True)
class UtilitiesDefaults:
    database_available: bool
    database_path: Path | None
    data_root: Path | None
    output_root: Path | None = None
    period_start: str | None = None
    period_end: str | None = None
    comparison_use_global_output: bool = True
    comparison_use_global_period: bool = True
    comparison_updated_at: str | None = None
    attachment_use_global_output: bool = True
    attachment_txt_max_lines: int = 10000
    attachment_updated_at: str | None = None
    att_data_repair_enabled: bool = True
    att_data_repair_use_global_output: bool = True
    att_data_repair_use_global_period: bool = True
    att_data_repair_generate_txt: bool = True
    att_data_repair_generate_excel_report: bool = True
    att_data_repair_txt_max_rows: int = 10000
    att_data_repair_updated_at: str | None = None
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class ComparisonRunRequest:
    attendance_source: Path
    outlook_source: Path
    workflow: str
    use_global_period: bool
    period_start: str | None
    period_end: str | None
    use_global_output: bool
    output_root: Path | None


@dataclass(frozen=True, slots=True)
class ComparisonResolvedRequest:
    job_id: str
    database_path: Path
    attendance_source: Path
    outlook_source: Path
    workflow: str
    period_start: str
    period_end: str
    output_root: Path
    used_global_period: bool
    used_global_output: bool


@dataclass(frozen=True, slots=True)
class ComparisonValidationResult:
    valid: bool
    attendance_reports: int
    outlook_reports: int
    expected_report_name: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    scan: object | None = None


@dataclass(frozen=True, slots=True)
class ComparisonProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class ComparisonLogEvent:
    timestamp: str
    level: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class ComparisonOutputFile:
    role: str
    path: Path


@dataclass(frozen=True, slots=True)
class ComparisonRunResult:
    success: bool
    cancelled: bool
    job_id: str
    started_at: str
    ended_at: str
    output_folder: Path | None
    outputs: tuple[ComparisonOutputFile, ...]
    total_records: int = 0
    attention_count: int = 0
    conflict_count: int = 0
    invalid_count: int = 0
    warning_count: int = 0
    status_breakdown: tuple[tuple[str, int], ...] = ()
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationRunRequest:
    source_folder: Path
    workflow: str
    mode: str
    scan_subfolders: bool
    use_global_output: bool
    output_root: Path | None
    txt_max_lines_override: int | None = None


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationResolvedRequest:
    job_id: str
    database_path: Path
    source_folder: Path
    workflow: str
    mode: str
    scan_subfolders: bool
    output_root: Path
    used_global_output: bool
    txt_max_lines: int


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationValidationResult:
    valid: bool
    total_files: int
    processable_files: int
    invalid_files: int
    duplicate_candidates: int
    subfolder_count: int
    txt_max_lines: int
    expected_output_root: Path
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    scan: object | None = None


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationLogEvent:
    timestamp: str
    level: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationOutputFile:
    role: str
    path: Path


@dataclass(frozen=True, slots=True)
class AttachmentConsolidationRunResult:
    success: bool
    cancelled: bool
    job_id: str
    started_at: str
    ended_at: str
    output_folder: Path | None
    outputs: tuple[AttachmentConsolidationOutputFile, ...]
    files_scanned: int = 0
    files_accepted: int = 0
    files_rejected: int = 0
    duplicates: int = 0
    output_txt_count: int = 0
    report_count: int = 0
    warning_count: int = 0
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class AttDataRepairRunRequest:
    source_report: Path | None
    use_global_period: bool
    period_start: str | None
    period_end: str | None
    use_global_output: bool
    output_root: Path | None
    generate_txt: bool
    generate_excel_report: bool
    source_report_folder: Path | None = None
    scan_recursive: bool = True


@dataclass(frozen=True, slots=True)
class AttDataRepairResolvedRequest:
    job_id: str
    database_path: Path
    source_report: Path
    period_start: str
    period_end: str
    output_root: Path
    used_global_period: bool
    used_global_output: bool
    generate_txt: bool
    generate_excel_report: bool
    settings: object
    source_report_folder: Path | None = None
    discovery: object | None = None

    @property
    def workflow(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class AttDataRepairValidationResult:
    valid: bool
    source_records: int
    valid_records_sheet: int
    invalid_records_sheet: int
    expected_output_root: Path
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    scan: object | None = None
    discovery_files_scanned: int = 0
    discovered_valid_reports: int = 0
    discovered_invalid_reports: int = 0


@dataclass(frozen=True, slots=True)
class AttDataRepairProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 100


@dataclass(frozen=True, slots=True)
class AttDataRepairLogEvent:
    timestamp: str
    level: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class AttDataRepairOutputFile:
    role: str
    path: Path


@dataclass(frozen=True, slots=True)
class AttDataRepairRunResult:
    success: bool
    cancelled: bool
    job_id: str
    started_at: str
    ended_at: str
    output_folder: Path | None
    outputs: tuple[AttDataRepairOutputFile, ...]
    source_records: int = 0
    final_records: int = 0
    changed_records: int = 0
    anomaly_records: int = 0
    txt_file_count: int = 0
    report_generated: bool = False
    warning_count: int = 0
    status: str = ""
    error_summary: str | None = None


class _CancellationToken:
    def __init__(self) -> None:
        self.event = threading.Event()

    @property
    def requested(self) -> bool:
        return self.event.is_set()

    def request(self) -> None:
        self.event.set()


class ComparisonCancellationToken(_CancellationToken):
    pass


class AttachmentConsolidationCancellationToken(_CancellationToken):
    pass


class AttDataRepairCancellationToken(_CancellationToken):
    pass
