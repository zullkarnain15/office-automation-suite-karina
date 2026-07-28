"""Reusable MM/DD/YYYY entry with a dependency-free Tk calendar picker."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

DISPLAY_DATE_FORMAT = "%m/%d/%Y"
ISO_DATE_FORMAT = "%Y-%m-%d"


def iso_to_display(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value, ISO_DATE_FORMAT).strftime(DISPLAY_DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Tanggal internal tidak valid: {value}") from exc


def display_to_iso(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, DISPLAY_DATE_FORMAT).strftime(ISO_DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Tanggal '{text}' tidak valid. Gunakan format MM/DD/YYYY."
        ) from exc


class DateEntry(ttk.Frame):
    """Entry and calendar button; the bound variable always uses MM/DD/YYYY."""

    def __init__(self, parent, *, textvariable: tk.StringVar, width: int = 12) -> None:
        super().__init__(parent)
        self.variable = textvariable
        self.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(
            self,
            textvariable=textvariable,
            width=width,
            style="Modern.TEntry",
        )
        self.entry.grid(row=0, column=0, sticky="ew")
        self.calendar_button = ttk.Button(
            self,
            text="📅",
            width=3,
            command=self.open_calendar,
        )
        self.calendar_button.grid(row=0, column=1, padx=(4, 0))

    def open_calendar(self) -> None:
        CalendarDialog(self, self.variable)

    def set_iso(self, value: str | None) -> None:
        self.variable.set(iso_to_display(value))

    def get_iso(self) -> str | None:
        return display_to_iso(self.variable.get())

    def set_state(self, state: str) -> None:
        self.entry.configure(
            state=state,
            style="Readonly.TEntry" if state in {"disabled", "readonly"} else "Modern.TEntry",
        )
        self.calendar_button.configure(
            state="disabled" if state in {"disabled", "readonly"} else "normal"
        )

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        result = super().configure(cnf, **kwargs)
        if state is not None:
            self.set_state(state)
        return result


class CalendarDialog(tk.Toplevel):
    def __init__(self, parent, variable: tk.StringVar) -> None:
        super().__init__(parent)
        self.variable = variable
        self.title("Pilih Tanggal")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        try:
            selected = datetime.strptime(variable.get(), DISPLAY_DATE_FORMAT).date()
        except ValueError:
            selected = date.today()
        self.year = selected.year
        self.month = selected.month
        self.header_var = tk.StringVar()
        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="both", expand=True)
        navigation = ttk.Frame(self.body)
        navigation.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 8))
        ttk.Button(navigation, text="‹", width=3, command=self._previous).pack(
            side="left"
        )
        ttk.Label(
            navigation,
            textvariable=self.header_var,
            anchor="center",
            width=20,
        ).pack(side="left", expand=True)
        ttk.Button(navigation, text="›", width=3, command=self._next).pack(
            side="right"
        )
        for column, label in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
            ttk.Label(self.body, text=label, anchor="center", width=4).grid(
                row=1, column=column
            )
        self.days = ttk.Frame(self.body)
        self.days.grid(row=2, column=0, columnspan=7)
        actions = ttk.Frame(self.body)
        actions.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Hari Ini", command=self._today).pack(side="left")
        ttk.Button(actions, text="Kosongkan", command=self._clear).pack(side="right")
        self._render()
        self.grab_set()

    def _render(self) -> None:
        for child in self.days.winfo_children():
            child.destroy()
        self.header_var.set(f"{calendar.month_name[self.month]} {self.year}")
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(
            self.year, self.month
        )
        for row, week in enumerate(weeks):
            for column, day in enumerate(week):
                if day:
                    ttk.Button(
                        self.days,
                        text=str(day),
                        width=4,
                        command=lambda value=day: self._select(value),
                    ).grid(row=row, column=column, padx=1, pady=1)
                else:
                    ttk.Label(self.days, text="", width=4).grid(
                        row=row, column=column
                    )

    def _previous(self) -> None:
        self.month -= 1
        if self.month == 0:
            self.month = 12
            self.year -= 1
        self._render()

    def _next(self) -> None:
        self.month += 1
        if self.month == 13:
            self.month = 1
            self.year += 1
        self._render()

    def _select(self, day: int) -> None:
        self.variable.set(date(self.year, self.month, day).strftime(DISPLAY_DATE_FORMAT))
        self.destroy()

    def _today(self) -> None:
        self.variable.set(date.today().strftime(DISPLAY_DATE_FORMAT))
        self.destroy()

    def _clear(self) -> None:
        self.variable.set("")
        self.destroy()
