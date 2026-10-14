"""Small reusable Previous/Next pagination control."""

from __future__ import annotations

from tkinter import ttk


class PaginationBar(ttk.Frame):
    def __init__(self, parent, previous, next_page):
        super().__init__(parent, style="OASK.TFrame")
        self.previous_button = ttk.Button(self, text="Previous", command=previous)
        self.previous_button.grid(row=0, column=0)
        self.label = ttk.Label(self, text="Page 1 / 1", style="SectionHeader.TLabel")
        self.label.grid(row=0, column=1, padx=12)
        self.next_button = ttk.Button(self, text="Next", command=next_page)
        self.next_button.grid(row=0, column=2)

    def update_state(self, *, offset: int, limit: int, total: int) -> None:
        current = offset // limit + 1
        pages = max(1, (total + limit - 1) // limit)
        self.label.configure(text=f"Page {current} / {pages}  •  {total} items")
        self.previous_button.configure(state="normal" if offset else "disabled")
        self.next_button.configure(
            state="normal" if offset + limit < total else "disabled"
        )
