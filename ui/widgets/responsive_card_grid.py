"""Scrollable two-column card grid that stacks at narrow content widths."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import MAIN_BACKGROUND, SPACE_MD


class ResponsiveCardGrid(ttk.Frame):
    def __init__(self, parent, *, breakpoint: int = 760) -> None:
        super().__init__(parent, style="OASK.TFrame")
        self.breakpoint = breakpoint
        self._cards: list[tuple[ttk.Widget, int, int, int, int, int]] = []
        self._narrow = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            background=MAIN_BACKGROUND,
        )
        scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self.canvas, style="OASK.TFrame")
        self.content.columnconfigure(0, weight=8, minsize=520)
        self.content.columnconfigure(1, weight=2, minsize=180)
        self._window = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw",
        )
        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize)

    def add(
        self,
        card: ttk.Widget,
        *,
        row: int,
        column: int,
        order: int,
        columnspan: int = 1,
        rowspan: int = 1,
    ) -> None:
        self._cards.append((card, row, column, columnspan, rowspan, order))
        self._layout()

    def _resize(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        narrow = event.width < self.breakpoint
        if narrow != self._narrow:
            self._narrow = narrow
            self._layout()

    def _layout(self) -> None:
        for card, *_ in self._cards:
            card.grid_forget()
        if self._narrow:
            for narrow_row, (card, *_rest) in enumerate(
                sorted(self._cards, key=lambda item: item[5])
            ):
                card.grid(
                    row=narrow_row,
                    column=0,
                    columnspan=2,
                    sticky="nsew",
                    padx=SPACE_MD,
                    pady=(SPACE_MD, 0),
                )
        else:
            for card, row, column, columnspan, rowspan, _order in self._cards:
                card.grid(
                    row=row,
                    column=column,
                    columnspan=columnspan,
                    rowspan=rowspan,
                    sticky="nsew",
                    padx=(SPACE_MD, 0) if column == 0 else SPACE_MD,
                    pady=(SPACE_MD, 0),
                )

    def _update_scroll_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
