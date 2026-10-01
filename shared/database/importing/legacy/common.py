"""Shared worksheet parsing helpers for legacy configuration mappers."""

from __future__ import annotations

from typing import Any

from shared.database.importing.models import CellData, SheetData


def key_value_rows(
    sheet: SheetData,
) -> dict[str, list[tuple[CellData, CellData | None]]]:
    """Return every parameter occurrence without hiding duplicate keys."""

    result: dict[str, list[tuple[CellData, CellData | None]]] = {}
    header_seen = False
    for row in sheet.rows:
        first = row[0] if row else None
        if first is None:
            continue
        if str(first.value).strip().casefold() == "parameter":
            header_seen = True
            continue
        if not header_seen or first.value is None:
            continue
        key = str(first.value).strip()
        value = row[1] if len(row) > 1 else None
        result.setdefault(key, []).append((first, value))
    return result


def table_rows(
    sheet: SheetData,
    *,
    required_header: str,
) -> list[dict[str, CellData]]:
    """Find a header row and return subsequent non-empty record rows."""

    headers: list[str] | None = None
    header_position = -1
    for position, row in enumerate(sheet.rows):
        values = [
            "" if cell.value is None else str(cell.value).strip()
            for cell in row
        ]
        if required_header in values:
            headers = values
            header_position = position
            break
    if headers is None:
        return []

    result: list[dict[str, CellData]] = []
    for row in sheet.rows[header_position + 1 :]:
        record = {
            header: row[index]
            for index, header in enumerate(headers)
            if header and index < len(row)
        }
        if any(cell.value is not None for cell in record.values()):
            result.append(record)
    return result


def value_of(
    values: dict[str, list[tuple[CellData, CellData | None]]],
    key: str,
    default: Any = None,
) -> Any:
    occurrences = values.get(key, ())
    if not occurrences or occurrences[0][1] is None:
        return default
    return occurrences[0][1].value


def split_values(value: Any) -> list[str]:
    if value is None:
        return []
    return [
        item.strip()
        for item in str(value).replace(",", ";").split(";")
        if item.strip()
    ]
