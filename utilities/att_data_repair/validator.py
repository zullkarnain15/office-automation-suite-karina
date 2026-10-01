"""Request validation for Att Data Repair."""

from __future__ import annotations

from datetime import time
from pathlib import Path

from utilities.att_data_repair.models import (
    AttDataRepairRequest,
    RequestValidationError,
)


def validate_request(request: AttDataRepairRequest) -> None:
    """Validate an Att Data Repair request without touching outputs."""

    source = Path(request.source_report)
    if source.suffix.casefold() != ".xlsx":
        raise RequestValidationError("Source report harus berupa file .xlsx.")
    if not source.is_file():
        raise RequestValidationError(f"Source report tidak ditemukan: {source}")
    if request.period_start > request.period_end:
        raise RequestValidationError(
            "Period Start tidak boleh setelah Period End."
        )
    if request.minimum_duration_minutes <= 0:
        raise RequestValidationError(
            "Minimum duration harus lebih besar dari nol."
        )
    for field_name in (
        "weekday_default_in",
        "weekday_default_out",
        "saturday_default_in",
        "saturday_default_out",
        "saturday_missing_out_default",
        "sunday_invalid_default_in",
        "sunday_invalid_default_out",
        "midnight_time_out_default",
    ):
        if not isinstance(getattr(request, field_name), time):
            raise RequestValidationError(f"{field_name} harus datetime.time.")
