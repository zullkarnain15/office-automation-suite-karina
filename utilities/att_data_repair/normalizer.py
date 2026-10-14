"""Normalization helpers for Att Data Repair."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from openpyxl.utils.datetime import from_excel

from utilities.att_data_repair.constants import (
    SPREADSHEET_ERRORS,
    WORKFLOW_BRANCH,
    WORKFLOW_HO,
)
from utilities.att_data_repair.models import (
    AttDataRepairRequest,
    NormalizedRecord,
    SourceRecord,
    TimeParseMetadata,
)
from utilities.att_data_repair.statuses import AnomalyCode, ChangeCode


@dataclass(frozen=True, slots=True)
class DateParseResult:
    value: date | None
    invalid_reason: str = ""


def normalize_record(
    source: SourceRecord,
    request: AttDataRepairRequest,
) -> NormalizedRecord:
    """Normalize one source row without applying repair rules."""

    invalid_codes: list[str] = []
    parsing_flags: list[str] = []
    workflow = normalize_workflow(source.workflow_raw)
    if workflow is None:
        invalid_codes.append(AnomalyCode.INVALID_WORKFLOW)

    nik = normalize_nik(source.nik_raw)
    if not nik:
        invalid_codes.append(AnomalyCode.INVALID_NIK)

    date_in = normalize_date(
        source.date_in_raw,
        request.period_start,
        request.period_end,
    )
    if date_in.value is None:
        invalid_codes.append(AnomalyCode.INVALID_DATE)

    date_out = normalize_date(
        source.date_out_raw,
        request.period_start,
        request.period_end,
    )

    time_in_meta = normalize_time(source.time_in_raw)
    time_out_meta = normalize_time(source.time_out_raw)
    if time_in_meta.normalized:
        parsing_flags.append(ChangeCode.TIME_FORMAT_NORMALIZED)
    if time_out_meta.normalized:
        parsing_flags.append(ChangeCode.TIME_FORMAT_NORMALIZED)

    return NormalizedRecord(
        source=source,
        workflow=workflow,
        nik=nik,
        date_in=date_in.value,
        time_in=time_in_meta.value,
        date_out=date_out.value,
        time_out=time_out_meta.value,
        parsing_flags=tuple(str(item) for item in parsing_flags),
        invalid_codes=tuple(str(item) for item in invalid_codes),
        time_in_meta=time_in_meta,
        time_out_meta=time_out_meta,
    )


def normalize_workflow(value: Any) -> str | None:
    """Return HO/Branch for safe workflow values only."""

    text = str(value or "").strip().casefold()
    if text == "ho":
        return WORKFLOW_HO
    if text == "branch":
        return WORKFLOW_BRANCH
    return None


def normalize_nik(value: Any) -> str:
    """Normalize NIK while preserving string leading zeroes."""

    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        text = value.strip()
        return "" if is_spreadsheet_error(text) else text
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return str(int(value)) if value.is_integer() else str(value).strip()
    text = str(value).strip()
    return "" if is_spreadsheet_error(text) else text


def normalize_date(
    value: Any,
    period_start: date,
    period_end: date,
) -> DateParseResult:
    """Parse dates conservatively using the report period as guard."""

    if value is None or isinstance(value, bool):
        return DateParseResult(None, "Tanggal kosong.")
    if isinstance(value, datetime):
        return DateParseResult(value.date())
    if isinstance(value, date):
        return DateParseResult(value)
    if isinstance(value, (int, float)):
        try:
            parsed = from_excel(value)
            if isinstance(parsed, datetime):
                return DateParseResult(parsed.date())
            if isinstance(parsed, date):
                return DateParseResult(parsed)
        except (TypeError, ValueError, OverflowError):
            return DateParseResult(None, "Serial date Excel tidak valid.")

    text = str(value or "").strip()
    if not text or is_spreadsheet_error(text):
        return DateParseResult(None, "Tanggal kosong atau spreadsheet error.")

    iso = _parse_iso(text)
    if iso is not None:
        return DateParseResult(iso)

    parts = re.split(r"[/-]", text)
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return _parse_three_part_date(parts, period_start, period_end)
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        return _parse_month_day_without_year(parts, period_start, period_end)

    return DateParseResult(None, f"Format tanggal tidak dikenali: {text}")


def normalize_time(value: Any) -> TimeParseMetadata:
    """Parse one time value and report whether text was normalized."""

    if value is None or isinstance(value, bool):
        return TimeParseMetadata(None, value, False, "Waktu kosong.")
    if isinstance(value, datetime):
        return TimeParseMetadata(value.time().replace(microsecond=0), value)
    if isinstance(value, time):
        return TimeParseMetadata(value.replace(microsecond=0), value)
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)) or value < 0:
            return TimeParseMetadata(None, value, False, "Waktu numeric invalid.")
        fraction = float(value) % 1
        seconds = round(fraction * 86_400) % 86_400
        parsed = (datetime.min + timedelta(seconds=seconds)).time()
        return TimeParseMetadata(parsed, value)

    text = str(value or "").strip()
    if not text or is_spreadsheet_error(text):
        return TimeParseMetadata(None, value, False, "Waktu kosong/error.")

    match = re.fullmatch(r"(\d{1,2})([:;.])(\d{1,2})(?::(\d{1,2}))?", text)
    if not match:
        return TimeParseMetadata(None, value, False, "Format waktu tidak dikenali.")
    hour = int(match.group(1))
    minute = int(match.group(3))
    second = int(match.group(4) or 0)
    if hour > 23 or minute > 59 or second > 59:
        return TimeParseMetadata(None, value, False, "Waktu di luar 00:00-23:59.")
    parsed = time(hour, minute)
    canonical = parsed.strftime("%H:%M")
    normalized = text != canonical
    return TimeParseMetadata(
        parsed,
        value,
        normalized,
        "Format waktu dinormalisasi." if normalized else "",
    )


def is_spreadsheet_error(value: Any) -> bool:
    return str(value or "").strip().upper() in SPREADSHEET_ERRORS


def format_date(value: date | None) -> str:
    return value.strftime("%m/%d/%Y") if value else ""


def format_time(value: time | None) -> str:
    return value.strftime("%H:%M") if value else ""


def minutes_from_time(value: time) -> int:
    return value.hour * 60 + value.minute


def time_from_minutes(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


def _parse_iso(text: str) -> date | None:
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
    except ValueError:
        return None
    return None


def _parse_three_part_date(
    parts: list[str],
    period_start: date,
    period_end: date,
) -> DateParseResult:
    first, second, third = parts
    if len(first) == 4:
        try:
            return DateParseResult(date(int(first), int(second), int(third)))
        except ValueError:
            return DateParseResult(None, "Tanggal tidak valid.")
    if len(third) != 4:
        return DateParseResult(None, "Tahun pendek tidak didukung.")

    month_or_day = int(first)
    day_or_month = int(second)
    year = int(third)
    if month_or_day > 12 and day_or_month <= 12:
        return _single_candidate(day_or_month, month_or_day, year)
    if day_or_month > 12 and month_or_day <= 12:
        return _single_candidate(month_or_day, day_or_month, year)
    candidates = _unique_valid_dates(
        (
            (month_or_day, day_or_month, year),
            (day_or_month, month_or_day, year),
        )
    )
    return _choose_by_period(candidates, period_start, period_end)


def _parse_month_day_without_year(
    parts: list[str],
    period_start: date,
    period_end: date,
) -> DateParseResult:
    if period_start.year != period_end.year:
        return DateParseResult(
            None,
            "Tanggal tanpa tahun ambigu pada periode lintas tahun.",
        )
    first, second = (int(part) for part in parts)
    year = period_start.year
    candidates = _unique_valid_dates(((first, second, year), (second, first, year)))
    return _choose_by_period(candidates, period_start, period_end)


def _single_candidate(month: int, day: int, year: int) -> DateParseResult:
    try:
        return DateParseResult(date(year, month, day))
    except ValueError:
        return DateParseResult(None, "Tanggal tidak valid.")


def _unique_valid_dates(candidates: tuple[tuple[int, int, int], ...]) -> tuple[date, ...]:
    dates = []
    for month, day, year in candidates:
        try:
            dates.append(date(year, month, day))
        except ValueError:
            continue
    return tuple(dict.fromkeys(dates))


def _choose_by_period(
    candidates: tuple[date, ...],
    period_start: date,
    period_end: date,
) -> DateParseResult:
    if len(candidates) == 1:
        return DateParseResult(candidates[0])
    in_period = [
        candidate
        for candidate in candidates
        if period_start <= candidate <= period_end
    ]
    if len(in_period) == 1:
        return DateParseResult(in_period[0])
    return DateParseResult(None, "Tanggal ambigu atau tidak dapat dipastikan.")
