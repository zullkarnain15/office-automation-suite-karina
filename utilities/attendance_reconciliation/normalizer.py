"""Normalization helpers for reconciliation source data."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from openpyxl.utils.datetime import from_excel


DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d")
TIME_FORMATS = ("%H:%M", "%H:%M:%S")


def normalize_workflow(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text == "ho":
        return "HO"
    if text == "branch":
        return "Branch"
    return ""


def normalize_nik(value: Any) -> str:
    """Normalize an NIK without inventing or stripping leading zeroes."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return str(int(value)) if value.is_integer() else str(value).strip()

    text = str(value).strip()
    if re.fullmatch(r"[+-]?\d+\.0", text):
        return text[:-2].lstrip("+")
    return text


def normalize_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = from_excel(value)
            return parsed.date() if isinstance(parsed, datetime) else parsed
        except (TypeError, ValueError, OverflowError):
            return None

    text = str(value or "").strip()
    if not text:
        return None
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def normalize_time(value: Any) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)) or value < 0:
            return None
        fraction = float(value) % 1
        seconds = round(fraction * 86_400) % 86_400
        return (datetime.min + timedelta(seconds=seconds)).time()

    text = str(value or "").strip()
    if not text:
        return None
    for time_format in TIME_FORMATS:
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue
    return None


def interpret_single_tap(
    check_in: Any,
    check_out: Any,
) -> tuple[time | None, time | None, time | None, str, str, str]:
    """Interpret one anomaly tap using the no-night-shift business rule."""
    normalized_in = normalize_time(check_in)
    normalized_out = normalize_time(check_out)
    populated = [
        ("Jam Masuk", normalized_in),
        ("Jam Keluar", normalized_out),
    ]
    taps = [(column, value) for column, value in populated if value is not None]
    if len(taps) != 1:
        return None, None, None, "", "", "INVALID_SINGLE_TAP_TIME"

    column, tap = taps[0]
    if tap <= time(12, 0):
        return tap, None, tap, column, "TIME_LE_12_AS_IN", "SINGLE_TAP_IN"
    return None, tap, tap, column, "TIME_GT_12_AS_OUT", "SINGLE_TAP_OUT"


def format_date(value: date | None) -> str:
    return value.strftime("%m/%d/%Y") if value else ""


def format_time(value: time | None) -> str:
    return value.strftime("%H:%M") if value else ""
