"""Small original 8-bit platform scene shared by operational modules."""

from __future__ import annotations

import tkinter as tk

from ui.theme.attendance_ot import DEFAULT_ATTENDANCE_OT_THEME


class RetroModuleBanner(tk.Canvas):
    """A compact, non-interactive scene that gives modules a shared identity."""

    def __init__(self, parent, *, title: str, height: int = 82) -> None:
        colors = DEFAULT_ATTENDANCE_OT_THEME.palette
        super().__init__(
            parent,
            height=height,
            background=colors.background,
            borderwidth=0,
            highlightthickness=0,
        )
        self._title = title.upper()
        self.bind("<Configure>", self._draw)

    def _draw(self, _event=None) -> None:
        colors = DEFAULT_ATTENDANCE_OT_THEME.palette
        width, height = max(self.winfo_width(), 640), max(self.winfo_height(), 82)
        self.delete("all")
        self.create_rectangle(0, 0, width, height, fill=colors.background, outline="")
        for x, y in ((42, 17), (width // 2 - 42, 10), (width - 255, 23)):
            self.create_rectangle(x, y + 7, x + 55, y + 18, fill=colors.card, outline="")
            self.create_rectangle(x + 12, y, x + 38, y + 24, fill=colors.card, outline="")
            self.create_rectangle(x + 39, y + 5, x + 67, y + 19, fill=colors.card, outline="")
        self.create_text(
            22,
            38,
            anchor="w",
            text=self._title,
            fill=colors.ink,
            font=("Segoe UI", 15, "bold"),
        )
        mushroom_x, mushroom_y = width - 112, 14
        self.create_rectangle(
            mushroom_x + 13,
            mushroom_y + 34,
            mushroom_x + 29,
            mushroom_y + 55,
            fill=colors.card,
            outline=colors.ink,
        )
        self.create_rectangle(
            mushroom_x + 3,
            mushroom_y + 23,
            mushroom_x + 39,
            mushroom_y + 39,
            fill=colors.tab_sage,
            outline=colors.ink,
        )
        self.create_rectangle(
            mushroom_x + 9,
            mushroom_y + 16,
            mushroom_x + 33,
            mushroom_y + 23,
            fill=colors.tab_sage,
            outline=colors.ink,
        )
        self.create_rectangle(mushroom_x + 10, mushroom_y + 26, mushroom_x + 16, mushroom_y + 32, fill=colors.card, outline="")
        self.create_rectangle(mushroom_x + 28, mushroom_y + 27, mushroom_x + 34, mushroom_y + 33, fill=colors.card, outline="")
        ground_y = height - 22
        self.create_rectangle(0, ground_y, width, height, fill=colors.tab_sage, outline=colors.ink)
        for x in range(-24, width + 24, 48):
            self.create_line(x, ground_y, x, height, fill=colors.ink, width=1)
            self.create_line(x + 24, ground_y + 11, x + 24, height, fill=colors.ink, width=1)
        self.create_line(0, ground_y + 11, width, ground_y + 11, fill=colors.ink, width=1)
