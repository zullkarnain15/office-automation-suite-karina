"""Compact chip-style choices for operational pages."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from ui.constants import OPTION_CHIP_SELECTED_FOREGROUND, SPACE_SM, TEXT_PRIMARY


class SegmentedChoice(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        variable: tk.StringVar,
        choices: Sequence[tuple[str, str]],
        command: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, style="ChoiceGroup.TFrame")
        self.variable = variable
        self.command = command
        self.buttons: dict[str, ttk.Label] = {}
        for index, (value, label) in enumerate(choices):
            widget = ttk.Label(
                self,
                text=label,
                style="ChoiceSegment.TLabel",
                cursor="hand2",
                anchor="center",
            )
            widget.grid(row=0, column=index, sticky="ew", padx=(0, SPACE_SM))
            widget.bind("<Button-1>", lambda _event, item=value: self.set(item))
            self.columnconfigure(index, weight=1)
            self.buttons[value] = widget
        self.variable.trace_add("write", lambda *_args: self._sync())
        self._sync()

    def set(self, value: str) -> None:
        self.variable.set(value)
        if self.command is not None:
            self.command()

    def _sync(self) -> None:
        selected = self.variable.get()
        for value, widget in self.buttons.items():
            widget.configure(
                style=(
                    "ChoiceSegmentSelected.TLabel"
                    if value == selected
                    else "ChoiceSegment.TLabel"
                )
            )


class OptionChip(ttk.Label):
    def __init__(
        self,
        parent,
        *,
        text: str,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            style="OptionChip.TLabel",
            cursor="hand2",
            anchor="center",
        )
        self.label = text
        self.variable = variable
        self.command = command
        self.bind("<Button-1>", lambda _event: self.toggle())
        self.variable.trace_add("write", lambda *_args: self._sync())
        self._sync()

    def toggle(self) -> None:
        self.variable.set(not self.variable.get())
        if self.command is not None:
            self.command()

    def _sync(self) -> None:
        if self.variable.get():
            self.configure(
                text=f"✓ {self.label}",
                style="OptionChipSelected.TLabel",
                foreground=OPTION_CHIP_SELECTED_FOREGROUND,
            )
        else:
            self.configure(
                text=f"  {self.label}",
                style="OptionChip.TLabel",
                foreground=TEXT_PRIMARY,
            )
