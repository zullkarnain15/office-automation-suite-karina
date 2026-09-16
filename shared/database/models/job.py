"""Typed operational job history models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JobHistoryRecord:
    """One normalized OAS-K job history row."""

    job_id: str
    module_code: str
    unified_status: str
    output_path_used: str
    used_global_output: bool
    used_global_period: bool
    created_at: str
    job_pk: int | None = None
    feature_code: str | None = None
    workflow: str | None = None
    legacy_status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    period_start_used: str | None = None
    period_end_used: str | None = None
    source_summary: str | None = None
    success_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    summary_json_path: str | None = None
    process_log_path: str | None = None
    error_message: str | None = None
    configuration_snapshot_hash: str | None = None


@dataclass(frozen=True, slots=True)
class JobFileRecord:
    """One external artifact reference associated with a job."""

    job_pk: int
    file_role: str
    file_path: str
    recorded_at: str
    job_file_id: int | None = None
    file_size: int | None = None
    file_hash: str | None = None
    exists_at_last_check: bool = True
    last_checked_at: str | None = None
