"""Structured operation result dialog without traceback exposure."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import (
    BORDER,
    CARD_BACKGROUND,
    CARD_BODY_FONT,
    IVORY_WHITE,
    ROYAL_BLUE,
    TEXT_PRIMARY,
)


class OperationResultDialog(tk.Toplevel):
    def __init__(self, parent, title: str, lines: tuple[str, ...]) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        frame = ttk.Frame(self, style="OASK.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        text = tk.Text(
            frame,
            width=80,
            height=18,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            selectbackground=ROYAL_BLUE,
            selectforeground=IVORY_WHITE,
            font=CARD_BODY_FONT,
            relief="solid",
            borderwidth=2,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            padx=12,
            pady=10,
        )
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(frame, text="Tutup", command=self.destroy).pack(
            anchor="e",
            pady=(12, 0),
        )
