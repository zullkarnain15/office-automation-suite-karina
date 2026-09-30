"""Typed contracts for Attendance & OT source scanning and import."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SourceType(StrEnum):
    ATTENDANCE_OT = "ATTENDANCE_OT"
    EMPLOYEE = "EMPLOYEE"
    SCHEDULE = "SCHEDULE"


class SourceStatus(StrEnum):
    NEW = "NEW"
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"
    ERROR = "ERROR"
    MISSING = "MISSING"


class ScheduleSubtype(StrEnum):
    ASSIGNMENT = "ASSIGNMENT"
    RULE = "RULE"


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    source_type: SourceType
    path: Path
    filename: str
    size_bytes: int
    modified_time_ns: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ScanIssue:
    source_type: SourceType
    path: Path
    filename: str
    error: str
    size_bytes: int = 0
    modified_time_ns: int = 0


@dataclass(frozen=True, slots=True)
class ParsedSourceRow:
    source_type: SourceType
    source_sheet: str
    source_row: int
    headers: dict[str, int]
    values: tuple[object, ...]
    schedule_subtype: ScheduleSubtype | None = None


@dataclass(frozen=True, slots=True)
class SourceRegistryItem:
    source_id: int
    source_type: str
    source_path: Path
    filename: str
    size_bytes: int
    modified_time_ns: int
    row_count: int
    status: str
    imported_at: str | None
    fingerprint: str | None
    error_detail: str | None


@dataclass(frozen=True, slots=True)
class RefreshProgress:
    phase: str
    message: str
    files_processed: int = 0
    files_skipped: int = 0
    files_error: int = 0
    rows_imported: int = 0


@dataclass(frozen=True, slots=True)
class RefreshResult:
    files_discovered: int
    files_processed: int
    files_skipped: int
    files_error: int
    files_missing: int
    rows_imported: int
    sources: tuple[SourceRegistryItem, ...]
    derived_rows: int = 0


@dataclass(frozen=True, slots=True)
class RefreshFileSummary:
    filename: str
    source_type: str
    status: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class RefreshPlan:
    files: tuple[RefreshFileSummary, ...]
    candidates: tuple[SourceCandidate, ...]
    scan_issues: tuple[ScanIssue, ...]
    scanned_types: frozenset[SourceType]
    folder_errors: int

    @property
    def changed_files(self) -> tuple[RefreshFileSummary, ...]:
        return tuple(item for item in self.files if item.status in {"NEW", "CHANGED"})

    def count(self, status: str) -> int:
        return sum(item.status == status for item in self.files)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    attendance_rows: int
    aggregate_rows: int
    full_rebuild: bool


@dataclass(frozen=True, slots=True)
class KpiSummary:
    total_records: int
    distinct_employees: int
    late_records: int
    total_ot_minutes: float
    total_ot_hours: float
    ot_amount: float
    meal_ot_amount: float
