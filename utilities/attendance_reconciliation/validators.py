"""Input and structure validation for reconciliation."""

from __future__ import annotations

from pathlib import Path

from utilities.attendance_reconciliation.models import ReconciliationRequest
from utilities.attendance_reconciliation.models import SOURCE_MODE_JOB
from utilities.attendance_reconciliation.models import SOURCE_MODE_SCAN


ATTENDANCE_DETAIL_HEADERS = {
    "NIK",
    "Nama",
    "Tanggal",
    "Jam Masuk",
    "Jam Keluar",
    "Tap Count",
}
ATTENDANCE_ANOMALY_HEADERS = ATTENDANCE_DETAIL_HEADERS | {"Pair Status"}
OUTLOOK_VALID_HEADERS = {
    "Workflow",
    "NIK",
    "Date_In",
    "Time_In",
    "Date_Out",
    "Time_Out",
}


def validate_request(request: ReconciliationRequest) -> None:
    if request.source_mode not in {SOURCE_MODE_SCAN, SOURCE_MODE_JOB}:
        raise ValueError("Source Mode is invalid.")
    if request.workflow not in {"HO", "Branch"}:
        raise ValueError("Workflow must be HO or Branch.")
    if request.start_date > request.end_date:
        raise ValueError("Start Date must be on or before End Date.")
    _require_folder(request.attendance_path, "Attendance source")
    _require_folder(request.outlook_path, "Outlook-Revisi source")
    try:
        request.output_folder.mkdir(parents=True, exist_ok=True)
        probe = request.output_folder / ".oas_k_write_probe"
        probe.touch(exist_ok=False)
        probe.unlink()
    except OSError as error:
        raise ValueError(
            f"Output Folder is not writable: {request.output_folder}"
        ) from error


def validate_headers(
    actual_headers: tuple[object, ...] | list[object],
    required_headers: set[str],
) -> list[str]:
    actual = {str(value or "").strip() for value in actual_headers}
    return sorted(required_headers - actual)


def _require_folder(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise ValueError(f"{label} folder is invalid: {path}")
