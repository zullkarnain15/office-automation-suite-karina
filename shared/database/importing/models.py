"""Typed contracts for Excel configuration detection, preview, and commit."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class WorkbookIdentity(StrEnum):
    ATTENDANCE_LEGACY = "ATTENDANCE_LEGACY"
    OUTLOOK_REVISI_LEGACY = "OUTLOOK_REVISI_LEGACY"
    HRIS_LEGACY = "HRIS_LEGACY"
    OAS_K_UNIFIED = "OAS_K_UNIFIED"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


class IssueSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ChangeOperation(StrEnum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UNCHANGED = "UNCHANGED"
    SKIP = "SKIP"


class ImportMode(StrEnum):
    REPLACE_MODULE_CONFIGURATION = "REPLACE_MODULE_CONFIGURATION"
    MERGE_REFERENCE_DATA = "MERGE_REFERENCE_DATA"
    UPDATE_GLOBAL_SETTINGS = "UPDATE_GLOBAL_SETTINGS"


@dataclass(frozen=True, slots=True)
class WorkbookDetectionResult:
    path: Path
    identity: WorkbookIdentity
    sheet_names: tuple[str, ...]
    sha256: str
    normalized_content_hash: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CellData:
    value: Any
    row_number: int
    column_number: int
    data_type: str
    number_format: str


@dataclass(frozen=True, slots=True)
class SheetData:
    name: str
    rows: tuple[tuple[CellData, ...], ...]


@dataclass(frozen=True, slots=True)
class WorkbookData:
    detection: WorkbookDetectionResult
    sheets: dict[str, SheetData]


@dataclass(frozen=True, slots=True)
class ConfigImportIssue:
    code: str
    severity: IssueSeverity
    module: str
    message: str
    sheet: str | None = None
    row_number: int | None = None
    field: str | None = None
    current_value: Any = None
    proposed_value: Any = None
    confirmation_required: bool = False


@dataclass(frozen=True, slots=True)
class ConfigImportChange:
    module: str
    setting_scope: str
    setting_key: str
    operation: ChangeOperation
    old_value: str | None
    new_value: str | None
    destructive: bool
    source_sheet: str | None = None
    source_row: int | None = None


@dataclass(frozen=True, slots=True)
class ConfigImportSectionPreview:
    module: str
    changes: tuple[ConfigImportChange, ...]
    issues: tuple[ConfigImportIssue, ...]


@dataclass(frozen=True, slots=True)
class MappedModuleConfiguration:
    module: str
    tables: dict[str, tuple[dict[str, Any], ...]]
    global_candidates: dict[str, Any] = field(default_factory=dict)
    source_file: Path | None = None
    source_hash: str = ""
    issues: tuple[ConfigImportIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfigImportPreview:
    source_files: tuple[Path, ...]
    detected_workbooks: tuple[WorkbookDetectionResult, ...]
    modules: tuple[str, ...]
    valid_count: int
    warning_count: int
    error_count: int
    critical_count: int
    confirmation_required: bool
    can_commit: bool
    changes: tuple[ConfigImportChange, ...]
    issues: tuple[ConfigImportIssue, ...]
    generated_at: str
    database_snapshot_hash: str
    mapped_modules: tuple[MappedModuleConfiguration, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfigImportCommitRequest:
    preview: ConfigImportPreview
    modules: tuple[str, ...]
    mode: ImportMode
    confirmed: bool = False
    operator: str | None = None
    global_resolution: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ConfigImportModuleResult:
    module: str
    committed: bool
    import_batch_id: int | None
    changes_applied: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigImportCommitResult:
    committed: bool
    module_results: tuple[ConfigImportModuleResult, ...]
    committed_at: str


@dataclass(frozen=True, slots=True)
class ConfigImportBatchRecord:
    module_code: str
    source_file_name: str
    source_file_hash: str
    import_mode: str
    started_at: str
    status: str
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    import_batch_id: int | None = None
    finished_at: str | None = None
    error_summary: str | None = None
    diagnostic_report_path: str | None = None
    operator: str | None = None
