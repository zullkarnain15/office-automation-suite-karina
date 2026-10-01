"""Typed contracts for data-root, Registry, and recorder-profile services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StartupStorageStatus(StrEnum):
    READY = "READY"
    AVAILABLE_NOT_REGISTERED = "AVAILABLE_NOT_REGISTERED"
    INITIAL_SETUP_REQUIRED = "INITIAL_SETUP_REQUIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
    INVALID_LOCATION = "INVALID_LOCATION"


@dataclass(frozen=True, slots=True)
class StoragePointer:
    data_root: Path
    database_path: Path


@dataclass(frozen=True, slots=True)
class StorageLayout:
    data_root: Path
    database_root: Path
    database_path: Path
    recorder_profiles_root: Path
    hris_recorder_profiles_root: Path
    backup_root: Path
    output_root: Path
    logs_root: Path
    diagnostics_root: Path

    @property
    def directories(self) -> tuple[Path, ...]:
        return (
            self.data_root,
            self.database_root,
            self.recorder_profiles_root,
            self.hris_recorder_profiles_root,
            self.backup_root,
            self.output_root,
            self.logs_root,
            self.diagnostics_root,
        )


@dataclass(frozen=True, slots=True)
class StorageValidationResult:
    path: Path
    exists: bool
    drive_available: bool
    writable: bool
    is_local: bool
    database_exists: bool
    database_valid: bool
    missing_directories: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def can_initialize(self) -> bool:
        return (
            self.drive_available
            and self.writable
            and self.is_local
            and not self.errors
            and (not self.database_exists or self.database_valid)
        )


@dataclass(frozen=True, slots=True)
class StorageBootstrapRequest:
    data_root: Path
    application_version: str
    update_registry: bool = True


@dataclass(frozen=True, slots=True)
class StorageBootstrapResult:
    success: bool
    data_root: Path
    database_path: Path
    created_directories: tuple[Path, ...]
    database_created: bool
    registry_updated: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StartupStorageResolution:
    status: StartupStorageStatus
    data_root: Path | None
    database_path: Path | None
    validation: StorageValidationResult | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataLocationChangeRequest:
    current_data_root: Path
    target_data_root: Path
    copy_database: bool = True
    copy_recorder_profiles: bool = True
    copy_output: bool = False
    copy_logs: bool = False
    overwrite_target_database: bool = False


@dataclass(frozen=True, slots=True)
class DataLocationChangeResult:
    success: bool
    source_data_root: Path
    target_data_root: Path
    target_database_path: Path
    database_copied: bool
    recorder_profiles_copied: int
    output_copied: bool
    logs_copied: bool
    registry_updated: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecorderProfileReference:
    relative_path: Path
    absolute_path: Path


@dataclass(frozen=True, slots=True)
class RecorderProfileValidationResult:
    reference: RecorderProfileReference | None
    exists: bool
    readable: bool
    json_object_valid: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
