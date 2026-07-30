"""Application backup and replacement primitives for the standalone updater."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


PROHIBITED_DATA_NAMES = {
    "database",
    "recorder_profiles",
    "logs",
    "backup",
    "backups",
    "output",
    "export",
    "update",
}


class ApplicationReplacementError(Exception):
    """Raised when application replacement cannot be completed safely."""


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_relative_to(path: str | Path, parent: str | Path) -> bool:
    value = resolved(path)
    root = resolved(parent)
    return value == root or root in value.parents


def reject_overlap(left: str | Path, right: str | Path, message: str) -> None:
    left_value = resolved(left)
    right_value = resolved(right)
    if (
        left_value == right_value
        or left_value in right_value.parents
        or right_value in left_value.parents
    ):
        raise ApplicationReplacementError(message)


def validate_application_paths(
    *,
    application_root: Path,
    staged_application_path: Path,
    rollback_path: Path,
    data_root: Path,
    entry_executable: str,
) -> None:
    app = resolved(application_root)
    staged = resolved(staged_application_path)
    rollback = resolved(rollback_path)
    data = resolved(data_root)
    if app == data:
        raise ApplicationReplacementError("Application Root equals Data Root.")
    if not app.is_dir():
        raise ApplicationReplacementError(f"Application Root missing: {app}")
    if not (app / entry_executable).is_file():
        raise ApplicationReplacementError(f"Old executable missing: {entry_executable}")
    if not staged.is_dir():
        raise ApplicationReplacementError(f"Staged application missing: {staged}")
    if not (staged / entry_executable).is_file():
        raise ApplicationReplacementError(f"Staged executable missing: {entry_executable}")
    reject_overlap(app, staged, "Staging and Application Root overlap.")
    reject_overlap(app, rollback, "Rollback path overlaps Application Root.")
    if not is_relative_to(rollback, data / "update" / "rollback"):
        raise ApplicationReplacementError("Rollback path outside Data Root/update/rollback.")
    if is_relative_to(data, app):
        raise ApplicationReplacementError(
            "Data Root is inside Application Root; automatic replacement is unsafe."
        )


def backup_application(
    *,
    application_root: Path,
    rollback_path: Path,
    data_root: Path,
    entry_executable: str,
) -> Path:
    source = resolved(application_root)
    rollback = resolved(rollback_path)
    data = resolved(data_root)
    if source == data:
        raise ApplicationReplacementError("Application Root equals Data Root.")
    if not source.is_dir():
        raise ApplicationReplacementError(f"Application Root missing: {source}")
    if not (source / entry_executable).is_file():
        raise ApplicationReplacementError(f"Old executable missing: {entry_executable}")
    reject_overlap(source, rollback, "Rollback path overlaps Application Root.")
    if is_relative_to(data, source):
        raise ApplicationReplacementError(
            "Data Root is inside Application Root; automatic backup is unsafe."
        )
    if not is_relative_to(rollback, data / "update" / "rollback"):
        raise ApplicationReplacementError("Rollback path outside Data Root/update/rollback.")
    destination = resolved(rollback_path) / "application"
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=_ignore_data_like_entries,
    )
    if not (destination / entry_executable).is_file():
        raise ApplicationReplacementError("Application backup validation failed.")
    return destination


def replace_application(
    *,
    application_root: Path,
    staged_application_path: Path,
    rollback_path: Path,
    data_root: Path,
    entry_executable: str,
) -> Path:
    validate_application_paths(
        application_root=application_root,
        staged_application_path=staged_application_path,
        rollback_path=rollback_path,
        data_root=data_root,
        entry_executable=entry_executable,
    )
    app = resolved(application_root)
    staged = resolved(staged_application_path)
    old_sibling = app.with_name(f"{app.name}.old")
    temp_target = app.with_name(f"{app.name}.new")
    for path in (old_sibling, temp_target):
        if path.exists():
            shutil.rmtree(path)
    shutil.copytree(staged, temp_target, symlinks=False)
    if not (temp_target / entry_executable).is_file():
        shutil.rmtree(temp_target, ignore_errors=True)
        raise ApplicationReplacementError("Temporary replacement validation failed.")
    try:
        os.replace(app, old_sibling)
        os.replace(temp_target, app)
    except Exception:
        if app.exists() and old_sibling.exists():
            failed = resolved(data_root) / "update" / "failed" / rollback_path.name / "application"
            failed.parent.mkdir(parents=True, exist_ok=True)
            if failed.exists():
                shutil.rmtree(failed)
            os.replace(app, failed)
        if old_sibling.exists() and not app.exists():
            os.replace(old_sibling, app)
        shutil.rmtree(temp_target, ignore_errors=True)
        raise
    shutil.rmtree(old_sibling, ignore_errors=True)
    return app


def _ignore_data_like_entries(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name.casefold() in PROHIBITED_DATA_NAMES
    }
