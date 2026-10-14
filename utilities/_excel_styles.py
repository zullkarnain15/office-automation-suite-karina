"""Workbook-local style templates for freshly created streaming cells."""
from __future__ import annotations

from copy import copy


def apply_data_style(cell, *, number_format=None, fill=None) -> None:
    """Apply the same public style setters once per distinct style combination.

    openpyxl stores workbook-specific style IDs in ``_style``. Cache only on
    the owning worksheet and copy the array for each cell: later changes to a
    cell must not change another cell or leak style IDs to another workbook.
    Include the initial style so automatic date/time formats are preserved.
    """
    sheet = cell.parent
    cache = getattr(sheet, "_oas_data_styles", None)
    if cache is None:
        cache = sheet._oas_data_styles = {}
    key = (tuple(cell._style or ()), number_format, id(fill))
    if key not in cache:
        if number_format:
            cell.number_format = number_format
        if fill is not None:
            cell.fill = fill
        # Retain fill as well so its identity cannot be reused while cached.
        cache[key] = (fill, copy(cell._style))
    else:
        cell._style = copy(cache[key][1])
