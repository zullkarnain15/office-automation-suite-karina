"""Typed UI4 Attendance adapter and service contracts."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AttendanceRunRequest:
    configuration_path: Path | None
    workflow: str
    use_global_output: bool
    use_global_period: bool
    override_output_root: Path | None
    override_period_start: str | None
    override_period_end: str | None
    generate_txt: bool = True
    generate_report: bool = True


@dataclass(frozen=True, slots=True)
class AttendanceResolvedRequest:
    job_id: str
    database_path: Path | None
    configuration_path: Path | None
    workflow: str
    output_root: Path
    period_start: str
    period_end: str
    used_global_output: bool
    used_global_period: bool
    generate_txt: bool
    generate_report: bool

    @property
    def configuration_source(self) -> str:
        return "EXCEL_FALLBACK" if self.configuration_path is not None else "SQLITE"


@dataclass(frozen=True, slots=True)
class AttendanceSourceValidation:
    name: str
    mdb_path: Path
    active: bool
    exists: bool
    readable: bool
    status: str


@dataclass(frozen=True, slots=True)
class AttendanceValidationResult:
    valid: bool
    configuration_valid: bool
    workflow: str
    active_mdb_count: int
    period_start: str
    period_end: str
    output_root: Path
    generate_txt: bool
    generate_report: bool
    sources: tuple[AttendanceSourceValidation, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AttendanceProgressEvent:
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class AttendanceLogEvent:
    timestamp: str
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class AttendanceOutputFile:
    file_type: str
    path: Path


@dataclass(frozen=True, slots=True)
class AttendanceRunResult:
    success: bool
    cancelled: bool
    job_id: str
    workflow: str
    started_at: str
    ended_at: str
    output_root: Path
    job_folder: Path | None
    output_files: tuple[AttendanceOutputFile, ...]
    record_counts: dict[str, int]
    warning_count: int = 0
    error_summary: str | None = None
    process_log_path: Path | None = None
    summary_json_path: Path | None = None


@dataclass(slots=True)
class AttendanceCancellationToken:
    _event: threading.Event = field(default_factory=threading.Event)

    def request(self) -> None:
        self._event.set()

    @property
    def requested(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class AttendanceDefaults:
    database_available: bool
    database_path: Path | None
    use_global_output: bool = False
    use_global_period: bool = False
    global_output_root: Path | None = None
    global_period_start: str | None = None
    global_period_end: str | None = None
    warning: str = ""
