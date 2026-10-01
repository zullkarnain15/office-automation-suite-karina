"""Central normalization for legacy and unified configuration values."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

TRUE_VALUES = {"TRUE", "YES", "Y", "1"}
FALSE_VALUES = {"FALSE", "NO", "N", "0"}


def normalize_boolean(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    text = str(value).strip().upper()
    if text in TRUE_VALUES:
        return 1
    if text in FALSE_VALUES:
        return 0
    raise ValueError(f"Unsupported boolean value: {value!r}")


def normalize_workflow(value: Any, *, allow_all: bool = False) -> str:
    text = str(value).strip().upper()
    allowed = {"HO", "BRANCH"}
    if allow_all:
        allowed.add("ALL")
    if text not in allowed:
        raise ValueError(f"Unsupported workflow value: {value!r}")
    return text


def normalize_date(value: Any, *, legacy_order: str | None = None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    parts = text.replace("-", "/").split("/")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Unsupported date value: {value!r}")
    first, second, year = (int(part) for part in parts)
    if len(parts[2]) != 4:
        raise ValueError(f"Ambiguous date value: {value!r}")
    if legacy_order == "MDY":
        month, day = first, second
    elif legacy_order == "DMY":
        day, month = first, second
    else:
        if first <= 12 and second <= 12:
            raise ValueError(f"Ambiguous date value: {value!r}")
        day, month = (
            (first, second) if first > 12 else (second, first)
        )
    return date(year, month, day).isoformat()


def normalize_path(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("Path must not be empty.")
    return text


def normalize_text_identifier(
    value: Any,
    *,
    number_format: str = "General",
) -> tuple[str, bool]:
    if isinstance(value, str):
        return value.strip(), False
    if isinstance(value, int):
        format_text = number_format.strip()
        if format_text and set(format_text) == {"0"}:
            return str(value).zfill(len(format_text)), False
        return str(value), True
    return str(value).strip(), True


def is_development_path(value: str) -> bool:
    text = value.casefold()
    return (
        "python project" in text
        or "\\temp\\" in text
        or "/temp/" in text
        or "sample" in text
    )


def is_local_url(value: str) -> bool:
    text = value.casefold()
    return (
        text.startswith("file://")
        or "localhost" in text
        or "127.0.0.1" in text
        or "mock" in text
    )


def is_gmail_test_address(value: str) -> bool:
    return value.strip().casefold().endswith("@gmail.com")


def path_exists(value: str) -> bool:
    return Path(value).exists()
