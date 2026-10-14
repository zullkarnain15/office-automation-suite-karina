"""Canonical Outlook payroll-period parsing and validation."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime

PAYROLL_PERIOD_PATTERN = re.compile(r"^(0[1-9]|1[0-2])-(\d{4})$")


def normalize_payroll_period(
    value: object,
    *,
    allow_blank: bool = False,
) -> str | None:
    if value is None or not str(value).strip():
        if allow_blank:
            return None
        raise ValueError("Payroll Period Outlook wajib diisi.")
    if isinstance(value, (date, datetime)):
        return value.strftime("%m-%Y")

    text = str(value).strip()
    if text.startswith("'"):
        text = text[1:].strip()
    match = PAYROLL_PERIOD_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(
            "Payroll Period Outlook harus memakai format MM-YYYY, contoh 07-2026."
        )
    return text


def payroll_period_dates(value: object) -> tuple[date, date]:
    normalized = normalize_payroll_period(value)
    assert normalized is not None
    month = int(normalized[:2])
    year = int(normalized[3:])
    return (
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1]),
    )
