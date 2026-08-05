"""Output artifact contracts for Att Data Repair jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AttDataRepairJobRequest:
    """Request for end-to-end non-GUI output generation."""

    analysis_request: Any
    output_root: Path
    txt_max_rows_per_file: int = 10_000
    generate_txt: bool = True
    generate_excel_report: bool = True


@dataclass(frozen=True, slots=True)
class JobPaths:
    """Reserved filesystem locations for one Att Data Repair job."""

    output_root: Path
    utilities_root: Path
    feature_root: Path
    job_folder: Path
    txt_folder: Path
    report_folder: Path
    process_log: Path
    summary_json: Path
    job_id: str


@dataclass(frozen=True, slots=True)
class TxtArtifact:
    """One generated HRIS TXT artifact."""

    workflow: str
    sequence: int
    unique_code: int
    file_name: str
    file_path: Path
    row_count: int
    record_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TxtWriteResult:
    """Result from writing all TXT files for a job."""

    artifacts: tuple[TxtArtifact, ...] = ()
    record_txt_assignment: dict[str, str] = field(default_factory=dict)
    unique_code: int | None = None


@dataclass(frozen=True, slots=True)
class ReportArtifact:
    """One generated Excel audit report artifact."""

    file_name: str
    file_path: Path
    sheet_names: tuple[str, ...]
    sheet_row_counts: dict[str, int]
    file_size_bytes: int


@dataclass(frozen=True, slots=True)
class AttDataRepairJobResult:
    """Complete result from a non-GUI Att Data Repair job."""

    job_id: str
    status: str
    paths: JobPaths
    analysis_result: Any
    txt_artifacts: tuple[TxtArtifact, ...]
    record_txt_assignment: dict[str, str]
    started_at: datetime
    completed_at: datetime
    error_message: str | None = None
    report_artifact: ReportArtifact | None = None
