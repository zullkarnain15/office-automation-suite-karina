"""Pure path resolution for the standard OAS-K storage layout."""

from __future__ import annotations

from pathlib import Path

from shared.storage.constants import (
    BACKUP_DIRECTORY,
    DATABASE_DIRECTORY,
    DATABASE_FILENAME,
    DIAGNOSTICS_DIRECTORY,
    HRIS_RECORDER_DIRECTORY,
    LOGS_DIRECTORY,
    OUTPUT_DIRECTORY,
    RECORDER_PROFILES_DIRECTORY,
)
from shared.storage.models import StorageLayout


def get_database_path(data_root: str | Path) -> Path:
    return Path(data_root) / DATABASE_DIRECTORY / DATABASE_FILENAME


def get_backup_root(data_root: str | Path) -> Path:
    return Path(data_root) / BACKUP_DIRECTORY


def get_output_root(data_root: str | Path) -> Path:
    return Path(data_root) / OUTPUT_DIRECTORY


def get_logs_root(data_root: str | Path) -> Path:
    return Path(data_root) / LOGS_DIRECTORY


def get_diagnostics_root(data_root: str | Path) -> Path:
    return Path(data_root) / DIAGNOSTICS_DIRECTORY


def get_recorder_profiles_root(data_root: str | Path) -> Path:
    return Path(data_root) / RECORDER_PROFILES_DIRECTORY


def get_hris_recorder_profiles_root(data_root: str | Path) -> Path:
    return get_recorder_profiles_root(data_root) / HRIS_RECORDER_DIRECTORY


def resolve_storage_layout(data_root: str | Path) -> StorageLayout:
    root = Path(data_root).expanduser()
    recorder_root = get_recorder_profiles_root(root)
    return StorageLayout(
        data_root=root,
        database_root=root / DATABASE_DIRECTORY,
        database_path=get_database_path(root),
        recorder_profiles_root=recorder_root,
        hris_recorder_profiles_root=(
            recorder_root / HRIS_RECORDER_DIRECTORY
        ),
        backup_root=get_backup_root(root),
        output_root=get_output_root(root),
        logs_root=get_logs_root(root),
        diagnostics_root=get_diagnostics_root(root),
    )
