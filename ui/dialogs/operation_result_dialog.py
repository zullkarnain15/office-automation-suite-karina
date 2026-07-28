"""Structured operation result dialog without traceback exposure."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class OperationResultDialog(tk.Toplevel):
    def __init__(self, parent, title: str, lines: tuple[str, ...]) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, width=80, height=18, wrap="word")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(frame, text="Tutup", command=self.destroy).pack(
            anchor="e",
            pady=(12, 0),
        )
