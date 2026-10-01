"""Data models for Attachment Consolidation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Callable

from outlook.parser import AttendanceRevisionRecord
from outlook.parser import OutlookDataAnomaly


MODE_EXCEL = "Merge Excel Attachment"
MODE_TXT = "Merge TXT Attachment"
SUPPORTED_MODES = (MODE_EXCEL, MODE_TXT)

ProgressCallback = Callable[[str, int, int, str], None]


class ConsolidationCancelled(RuntimeError):
    """Raised when an operator requests cancellation."""


@dataclass(slots=True)
class ConsolidationRequest:
    mode: str
    workflow: str
    source_root: Path
    output_root: Path
    scan_subfolders: bool = True
    configuration_file: Path | None = None

    def fingerprint(self) -> tuple[str, ...]:
        return (
            self.mode,
            self.workflow,
            str(self.source_root.resolve()),
            str(self.output_root.resolve()),
            str(bool(self.scan_subfolders)),
            str(self.configuration_file.resolve())
            if self.configuration_file is not None
            else "",
        )


@dataclass(slots=True)
class ScannedAttachment:
    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    status: str
    reason: str = ""

    @property
    def processable(self) -> bool:
        return self.status == "READY"


@dataclass(slots=True)
class ConsolidationScan:
    request_fingerprint: tuple[str, ...]
    files: list[ScannedAttachment]
    warnings: list[str] = field(default_factory=list)

    @property
    def processable_files(self) -> list[ScannedAttachment]:
        return [item for item in self.files if item.processable]


@dataclass(slots=True)
class ConsolidationFileResult:
    scanned: ScannedAttachment
    status: str
    row_read: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    empty_row_dropped: int = 0
    message: str = ""
    output_files: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class ConsolidationArtifacts:
    job_id: str
    job_folder: Path
    txt_folder: Path
    report_folder: Path
    report_file: Path
    process_log: Path
    summary_json: Path


@dataclass(slots=True)
class ConsolidationResult:
    success: bool
    request: ConsolidationRequest
    scan: ConsolidationScan
    artifacts: ConsolidationArtifacts
    file_results: list[ConsolidationFileResult]
    records: list[AttendanceRevisionRecord]
    anomalies: list[OutlookDataAnomaly]
    output_files: list[Path]
    max_lines: int
    started_at: datetime
    finished_at: datetime
    error_message: str = ""
    cancelled: bool = False

    @property
    def duration_seconds(self) -> float:
        return max(
            0.0,
            (self.finished_at - self.started_at).total_seconds(),
        )


def check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ConsolidationCancelled(
            "Attachment Consolidation dibatalkan oleh operator."
        )
