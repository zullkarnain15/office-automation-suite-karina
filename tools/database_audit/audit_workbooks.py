"""Read-only structural audit for OAS-K Excel configuration workbooks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_ROOT = PROJECT_ROOT / "config"


def serialize_value(value: Any) -> Any:
    """Convert Excel-supported values to JSON-compatible values."""

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def normalize_key(value: Any) -> str:
    """Normalize a possible configuration key for duplicate detection."""

    return str(value).strip().casefold()


def first_populated_row(cells: list[Cell]) -> int | None:
    """Return the first row number containing at least one value."""

    populated_rows = sorted({cell.row for cell in cells})
    return populated_rows[0] if populated_rows else None


def duplicate_values(values: list[Any]) -> list[str]:
    """Return normalized duplicate non-empty values."""

    normalized = [
        normalize_key(value)
        for value in values
        if value is not None and str(value).strip()
    ]
    return sorted(key for key, count in Counter(normalized).items() if count > 1)


def audit_sheet(sheet: Any) -> dict[str, Any]:
    """Collect structural and cell metadata for one worksheet."""

    cells = [
        cell
        for row in sheet.iter_rows()
        for cell in row
        if cell.value is not None
    ]
    header_row = first_populated_row(cells)
    header_values: list[Any] = []
    if header_row is not None:
        header_values = [
            sheet.cell(header_row, column).value
            for column in range(1, sheet.max_column + 1)
        ]

    first_column_values = [
        sheet.cell(row, 1).value
        for row in range((header_row or 0) + 1, sheet.max_row + 1)
    ]
    validations = []
    for validation in sheet.data_validations.dataValidation:
        validations.append(
            {
                "ranges": str(validation.sqref),
                "type": validation.type,
                "operator": validation.operator,
                "formula1": validation.formula1,
                "formula2": validation.formula2,
                "allow_blank": validation.allow_blank,
            }
        )

    return {
        "title": sheet.title,
        "state": sheet.sheet_state,
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "freeze_panes": str(sheet.freeze_panes or ""),
        "merged_ranges": [str(item) for item in sheet.merged_cells.ranges],
        "auto_filter": str(sheet.auto_filter.ref or ""),
        "tables": sorted(sheet.tables),
        "data_validations": validations,
        "duplicate_headers": duplicate_values(header_values),
        "duplicate_first_column_keys": duplicate_values(first_column_values),
        "cells": [
            {
                "coordinate": cell.coordinate,
                "value": serialize_value(cell.value),
                "data_type": cell.data_type,
                "number_format": cell.number_format,
            }
            for cell in cells
        ],
    }


def audit_workbook(path: Path) -> dict[str, Any]:
    """Open one workbook without saving and return its audit payload."""

    workbook = load_workbook(
        path,
        data_only=False,
        read_only=False,
        keep_links=True,
    )
    try:
        defined_names = []
        for item in workbook.defined_names.values():
            defined_names.append(
                {
                    "name": item.name,
                    "attr_text": item.attr_text,
                    "hidden": item.hidden,
                }
            )

        return {
            "path": str(path.resolve()),
            "sheet_names": workbook.sheetnames,
            "defined_names": defined_names,
            "external_link_count": len(workbook._external_links),
            "calculation_mode": workbook.calculation.fullCalcOnLoad,
            "sheets": [audit_sheet(sheet) for sheet in workbook.worksheets],
        }
    finally:
        workbook.close()


def find_workbooks(config_root: Path) -> list[Path]:
    """Find current Excel configuration workbooks."""

    return sorted(
        path
        for path in config_root.rglob("*.xlsx")
        if not path.name.startswith("~$")
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit OAS-K Excel configuration workbooks read-only.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional workbook paths. Defaults to every .xlsx under config/.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    paths = arguments.paths or find_workbooks(DEFAULT_CONFIG_ROOT)
    payload = {
        "audit_mode": "read-only",
        "workbooks": [audit_workbook(path) for path in paths],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
