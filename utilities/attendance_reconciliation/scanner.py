"""Safe recursive report discovery for reconciliation."""

from __future__ import annotations

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

    for path in sorted(root.rglob(pattern), key=lambda item: str(item).casefold()):
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

    # rglob("Export...") does not match the ~$ prefix, so inspect only lock
    # file variants of the known pattern instead of every xlsx workbook.
    lock_pattern = "~$" + pattern
    for path in sorted(root.rglob(lock_pattern), key=lambda item: str(item).casefold()):
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
