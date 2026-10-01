"""Safe recursive report discovery for reconciliation."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from threading import Event

from utilities.attendance_reconciliation.models import ScanLogEntry
from utilities.attendance_reconciliation.models import check_cancelled


ATTENDANCE_PATTERN = "Export_Attendance_*.xlsx"
OUTLOOK_PATTERN = "Outlook_Process_Report_*.xlsx"
IGNORED_FOLDER_NAMES = {
    "attachments",
    "txt",
    "uploaded",
    "archive",
    "archives",
    "temp",
    "temporary",
    "backup",
    "backups",
    "build",
    "dist",
    "__pycache__",
}


def discover_reports(
    root: Path,
    source_type: str,
    cancel_event: Event | None = None,
) -> tuple[list[Path], list[ScanLogEntry]]:
    """Discover only known source report names beneath a selected folder."""
    pattern = ATTENDANCE_PATTERN if source_type == "Attendance" else OUTLOOK_PATTERN
    candidates: list[Path] = []
    preliminary_logs: list[ScanLogEntry] = []

    report_paths, lock_paths = _discover_paths(root, pattern, cancel_event)
    for path in report_paths:
        check_cancelled(cancel_event)
        if _is_ignored_path(path, root):
            continue
        if path.name.startswith("~$"):
            preliminary_logs.append(
                ScanLogEntry(
                    source_type=source_type,
                    file_path=path,
                    workflow_detected=detect_workflow(path),
                    status="TEMPORARY_FILE",
                    reason="Temporary Excel lock file ignored.",
                )
            )
            continue
        try:
            if path.stat().st_size == 0:
                preliminary_logs.append(
                    ScanLogEntry(
                        source_type=source_type,
                        file_path=path,
                        workflow_detected=detect_workflow(path),
                        status="INVALID",
                        reason="Empty workbook ignored.",
                    )
                )
                continue
        except OSError as error:
            preliminary_logs.append(
                ScanLogEntry(
                    source_type=source_type,
                    file_path=path,
                    workflow_detected=detect_workflow(path),
                    status="LOCKED_FILE",
                    reason=str(error),
                )
            )
            continue
        candidates.append(path)

    for path in lock_paths:
        check_cancelled(cancel_event)
        if _is_ignored_path(path, root):
            continue
        preliminary_logs.append(
            ScanLogEntry(
                source_type=source_type,
                file_path=path,
                workflow_detected=detect_workflow(path),
                status="TEMPORARY_FILE",
                reason="Temporary Excel lock file ignored.",
            )
        )

    return candidates, preliminary_logs


def _discover_paths(root: Path, pattern: str, cancel_event: Event | None):
    reports: list[Path] = []
    locks: list[Path] = []
    lock_pattern = "~$" + pattern
    # Prune excluded subtrees before descending; retain the original sorted
    # report order and append lock-file audit entries after report errors.
    for folder, directories, files in os.walk(root, followlinks=False):
        check_cancelled(cancel_event)
        for name in (*directories, *files):
            check_cancelled(cancel_event)
            if fnmatch.fnmatch(name, pattern):
                reports.append(Path(folder) / name)
            elif fnmatch.fnmatch(name, lock_pattern):
                locks.append(Path(folder) / name)
        directories[:] = [
            name for name in directories if name.casefold() not in IGNORED_FOLDER_NAMES
        ]
    key = lambda path: str(path).casefold()
    return sorted(reports, key=key), sorted(locks, key=key)


def detect_workflow(path: Path) -> str:
    tokens = [part.casefold() for part in path.parts]
    name = path.name.casefold()
    if "ho" in tokens or "_ho_" in name:
        return "HO"
    if "branch" in tokens or "_branch_" in name:
        return "Branch"
    return ""


def _is_ignored_path(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts[:-1]
    except ValueError:
        relative_parts = path.parts[:-1]
    return any(part.casefold() in IGNORED_FOLDER_NAMES for part in relative_parts)
