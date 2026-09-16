"""Read-only validation for data roots and database candidates."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from shared.database import DatabaseValidator
from shared.database.models import DatabaseValidationResult
from shared.storage.models import StorageValidationResult
from shared.storage.path_resolver import resolve_storage_layout

logger = logging.getLogger(__name__)


def validate_data_root(
    path: str | Path,
    *,
    database_validator: DatabaseValidator | None = None,
) -> StorageValidationResult:
    """Validate a candidate without creating any file or directory."""

    root = Path(path).expanduser()
    layout = resolve_storage_layout(root)
    exists = root.exists()
    is_directory = root.is_dir() if exists else True
    is_local = not _is_network_path(root)
    drive_available = _drive_available(root)
    writable = (
        is_directory
        and drive_available
        and _nearest_existing_parent_writable(root)
    )
    missing = tuple(
        directory
        for directory in layout.directories
        if not directory.is_dir()
    )
    database_exists = layout.database_path.is_file()
    database_valid = False
    warnings: list[str] = []
    errors: list[str] = []

    if not drive_available:
        errors.append("Target drive or filesystem root is unavailable.")
    if not is_local:
        errors.append("Active Data Root must be on a local path.")
    if exists and not is_directory:
        errors.append("Data Root path points to a file.")
    if drive_available and is_local and not writable:
        errors.append("Data Root or its parent is not writable.")
    if not exists and drive_available and writable:
        warnings.append("Data Root does not exist and requires bootstrap.")
    if missing:
        warnings.append("One or more standard directories are missing.")

    if database_exists:
        validation = (database_validator or DatabaseValidator()).validate(
            layout.database_path
        )
        database_valid = validation.is_valid
        if not database_valid:
            errors.append(
                "Existing OAS-K database is invalid: "
                + "; ".join(validation.errors)
            )
    else:
        warnings.append("OAS-K database does not exist.")

    result = StorageValidationResult(
        path=root,
        exists=exists,
        drive_available=drive_available,
        writable=writable,
        is_local=is_local,
        database_exists=database_exists,
        database_valid=database_valid,
        missing_directories=missing,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )
    logger.info(
        "Storage validation completed: path=%s usable=%s",
        root,
        result.can_initialize,
    )
    return result


def validate_existing_database_candidate(
    path: str | Path,
    *,
    database_validator: DatabaseValidator | None = None,
) -> DatabaseValidationResult:
    """Validate only; never copy, migrate, or activate the candidate."""

    candidate = Path(path).expanduser()
    result = (database_validator or DatabaseValidator()).validate(candidate)
    logger.info(
        "Existing database candidate validation: path=%s valid=%s",
        candidate,
        result.is_valid,
    )
    return result


def _is_network_path(path: Path) -> bool:
    text = str(path)
    return text.startswith("\\\\") or text.startswith("//")


def _drive_available(path: Path) -> bool:
    if _is_network_path(path):
        return False
    anchor = path.anchor
    if not anchor:
        return False
    return Path(anchor).exists()


def _nearest_existing_parent_writable(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)
