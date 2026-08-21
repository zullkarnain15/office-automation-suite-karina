"""Typed models for manual OAS-K application update packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SUPPORTED_PACKAGE_FORMATS = frozenset({1})
APPLICATION_ID = "oas-k"
APPLICATION_NAME = "Office Automation Suite - Karina"
PACKAGE_TYPE_APPLICATION_ONLY = "application_only"
ENTRY_EXECUTABLE = "OAS-K.exe"
PENDING_STATUS_STAGED = "STAGED"
CANCELLED_STATUS = "CANCELLED"
TERMINAL_TRANSACTION_STATUSES = frozenset(
    {"SUCCESS", "ROLLED_BACK", "FAILED", CANCELLED_STATUS}
)
NON_TERMINAL_TRANSACTION_STATUSES = frozenset(
    {
        "STAGED",
        "APPLY_REQUESTED",
        "WAITING_FOR_SHUTDOWN",
        "BACKING_UP_APPLICATION",
        "APPLYING",
        "APPLICATION_REPLACED",
        "STARTING_NEW_APPLICATION",
        "HEALTHCHECK_PENDING",
        "ROLLBACK_REQUESTED",
        "ROLLBACK_IN_PROGRESS",
    }
)
TRANSACTION_STATUSES = TERMINAL_TRANSACTION_STATUSES | NON_TERMINAL_TRANSACTION_STATUSES


@dataclass(frozen=True, slots=True)
class UpdatePackageManifest:
    package_format: int
    application_id: str
    application_name: str
    version: str
    minimum_current_version: str
    package_type: str
    database_schema_from: int
    database_schema_to: int
    migration_required: bool
    created_at: str
    entry_executable: str


@dataclass(frozen=True, slots=True)
class UpdatePackageInfo:
    package_path: Path
    manifest: UpdatePackageManifest
    package_sha256: str
    file_count: int
    total_uncompressed_size: int


@dataclass(frozen=True, slots=True)
class UpdateValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    info: UpdatePackageInfo | None = None


@dataclass(frozen=True, slots=True)
class PreparedUpdateResult:
    status: str
    current_version: str
    target_version: str
    package_path: Path
    staging_path: Path
    backup_path: Path
    prepared_at: str
    package_sha256: str
    pending_path: Path
    transaction_id: str | None = None
    transaction_path: Path | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class UpdateTransaction:
    transaction_id: str
    status: str
    current_version: str
    target_version: str
    package_path: Path
    package_sha256: str
    staging_path: Path
    staged_application_path: Path
    application_root: Path
    rollback_path: Path
    database_backup_path: Path
    entry_executable: str
    created_at: str
    updated_at: str
    transaction_path: Path | None = None
    source_process_id: int | None = None
    new_process_id: int | None = None
    last_error: str | None = None
    log_path: Path | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_TRANSACTION_STATUSES


@dataclass(frozen=True, slots=True)
class ApplyRequestResult:
    transaction: UpdateTransaction
    updater_path: Path
    process_id: int
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    transaction_id: str
    status: Literal["SUCCESS", "FAILED"]
    application_version: str
    database_schema_version: int | None
    checked_at: str
    checks: dict[str, bool]
    marker_path: Path | None = None
    errors: tuple[str, ...] = ()
