"""Typed data contracts for Att Data Repair Sprint 2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any

from utilities.att_data_repair.constants import (
    DEFAULT_MINIMUM_DURATION_MINUTES,
    MIDNIGHT_TIME_OUT_DEFAULT,
    SATURDAY_DEFAULT_IN,
    SATURDAY_DEFAULT_OUT,
    SATURDAY_MISSING_OUT_DEFAULT,
    SUNDAY_INVALID_DEFAULT_IN,
    SUNDAY_INVALID_DEFAULT_OUT,
    WEEKDAY_DEFAULT_IN,
    WEEKDAY_DEFAULT_OUT,
)


class AttDataRepairError(RuntimeError):
    """Base exception for Att Data Repair failures."""


class RequestValidationError(AttDataRepairError):
    """Raised when the in-memory request is invalid."""


class SourceWorkbookError(AttDataRepairError):
    """Raised when the source workbook cannot be used."""


class ReportDiscoveryError(AttDataRepairError):
    """Raised when source folder discovery cannot produce a safe selection."""


class MissingRequiredSheetError(SourceWorkbookError):
    """Raised when a required Attachment Consolidation sheet is missing."""


class MissingRequiredColumnError(SourceWorkbookError):
    """Raised when a required Attachment Consolidation column is missing."""


class JobFolderCreationError(AttDataRepairError):
    """Raised when a job folder cannot be reserved."""


class OutputWriteError(AttDataRepairError):
    """Raised when an output artifact cannot be written."""


class TxtWriteError(OutputWriteError):
    """Raised when HRIS TXT output cannot be written safely."""


class UniqueCodeCollisionError(TxtWriteError):
    """Raised when no collision-free TXT unique code can be found."""


class SummaryWriteError(OutputWriteError):
    """Raised when summary.json cannot be written safely."""


class ReportWriteError(OutputWriteError):
    """Raised when Excel report output cannot be written safely."""


class ReportAlreadyExistsError(ReportWriteError):
    """Raised when an Excel report target already exists."""


@dataclass(frozen=True, slots=True)
class AttDataRepairRequest:
    """In-memory request for Sprint 2 analysis only."""

    source_report: Path
    period_start: date
    period_end: date
    minimum_duration_minutes: int = DEFAULT_MINIMUM_DURATION_MINUTES
    weekday_default_in: time = WEEKDAY_DEFAULT_IN
    weekday_default_out: time = WEEKDAY_DEFAULT_OUT
    saturday_default_in: time = SATURDAY_DEFAULT_IN
    saturday_default_out: time = SATURDAY_DEFAULT_OUT
    saturday_missing_out_default: time = SATURDAY_MISSING_OUT_DEFAULT
    sunday_invalid_default_in: time = SUNDAY_INVALID_DEFAULT_IN
    sunday_invalid_default_out: time = SUNDAY_INVALID_DEFAULT_OUT
    midnight_time_out_default: time = MIDNIGHT_TIME_OUT_DEFAULT


@dataclass(frozen=True, slots=True)
class ReportDiscoveryCandidate:
    """One Excel candidate found while scanning a source report folder."""

    path: Path
    relative_path: str
    status: str
    reason: str
    record_count: int = 0
    valid_records_count: int = 0
    invalid_records_count: int = 0
    size_bytes: int = 0

    @property
    def valid(self) -> bool:
        return self.status == "VALID"


@dataclass(frozen=True, slots=True)
class ReportDiscoveryResult:
    """Read-only inventory from source report folder discovery."""

    source_folder: Path
    recursive: bool
    candidates: tuple[ReportDiscoveryCandidate, ...] = ()
    skipped_temp_files: int = 0

    @property
    def files_scanned(self) -> int:
        return len(self.candidates)

    @property
    def valid_candidates(self) -> tuple[ReportDiscoveryCandidate, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.valid)

    @property
    def invalid_candidates(self) -> tuple[ReportDiscoveryCandidate, ...]:
        return tuple(candidate for candidate in self.candidates if not candidate.valid)


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One raw row read from Valid_Records or Invalid_Records."""

    record_id: str
    source_workbook: Path
    source_sheet: str
    source_record_no: Any
    source_file: str
    relative_path: str
    source_row: Any
    workflow_raw: Any
    nik_raw: Any
    date_in_raw: Any
    time_in_raw: Any
    date_out_raw: Any
    time_out_raw: Any
    source_status: str
    source_reason: str
    raw_value: str


@dataclass(frozen=True, slots=True)
class TimeParseMetadata:
    """Time parse value with audit metadata."""

    value: time | None
    original_value: Any
    normalized: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    """One source row after normalization, before repair rules."""

    source: SourceRecord
    workflow: str | None
    nik: str
    date_in: date | None
    time_in: time | None
    date_out: date | None
    time_out: time | None
    parsing_flags: tuple[str, ...] = ()
    invalid_codes: tuple[str, ...] = ()
    time_in_meta: TimeParseMetadata | None = None
    time_out_meta: TimeParseMetadata | None = None

    @property
    def record_id(self) -> str:
        return self.source.record_id


@dataclass(frozen=True, slots=True)
class RepairChange:
    """One deterministic field-level repair action."""

    record_id: str
    field_name: str
    original_value: str
    final_value: str
    change_code: str
    reason: str


@dataclass(frozen=True, slots=True)
class RepairAnomaly:
    """One record excluded from final records."""

    record_id: str
    anomaly_code: str
    reason: str
    action: str
    source: SourceRecord

    @property
    def lineage(self) -> SourceRecord:
        return self.source


@dataclass(frozen=True, slots=True)
class FinalRecord:
    """One record eligible for future TXT/report export."""

    record_id: str
    workflow: str
    nik: str
    date_in: date
    time_in: time
    date_out: date
    time_out: time
    duration_minutes: int
    source_sheet: str
    source_file: str
    source_row: Any
    final_status: str
    changes: tuple[RepairChange, ...] = ()


@dataclass(frozen=True, slots=True)
class AttDataRepairAnalysisResult:
    """Complete in-memory result from Sprint 2 analysis."""

    final_records: tuple[FinalRecord, ...] = ()
    changed_records: tuple[FinalRecord, ...] = ()
    anomalies: tuple[RepairAnomaly, ...] = ()
    change_log: tuple[RepairChange, ...] = ()
    source_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    source_records: tuple[SourceRecord, ...] = ()
