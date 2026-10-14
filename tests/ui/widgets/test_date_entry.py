from __future__ import annotations

import tkinter as tk

import pytest

from ui.widgets.date_entry import DateEntry, display_to_iso, iso_to_display


@pytest.mark.parametrize(
    "iso_value,display_value",
    [
        ("2026-07-01", "07/01/2026"),
        ("2024-02-29", "02/29/2024"),
        (None, ""),
    ],
)
def test_iso_and_display_date_conversion(iso_value, display_value) -> None:
    assert iso_to_display(iso_value) == display_value
    assert display_to_iso(display_value) == iso_value


@pytest.mark.parametrize("value", ["2026-07-01", "31/07/2026", "02/30/2026"])
def test_display_date_rejects_non_mm_dd_yyyy_values(value: str) -> None:
    with pytest.raises(ValueError, match="MM/DD/YYYY"):
        display_to_iso(value)


def test_date_entry_has_calendar_button_and_preserves_iso_boundary(tk_root) -> None:
    variable = tk.StringVar(master=tk_root)
    widget = DateEntry(tk_root, textvariable=variable)
    widget.set_iso("2026-07-31")
    assert variable.get() == "07/31/2026"
    assert widget.get_iso() == "2026-07-31"
    assert widget.calendar_button.cget("text") == "📅"


def test_readonly_disables_calendar_button(tk_root) -> None:
    variable = tk.StringVar(master=tk_root)
    widget = DateEntry(tk_root, textvariable=variable)
    widget.set_state("readonly")
    assert str(widget.entry.cget("state")) == "readonly"
    assert str(widget.calendar_button.cget("state")) == "disabled"
