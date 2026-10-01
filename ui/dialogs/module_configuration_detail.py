"""Read-only, detail-on-demand view for active module configuration."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ModuleConfigurationDetailDialog(tk.Toplevel):
    def __init__(self, parent, detail) -> None:
        super().__init__(parent)
        self.title(f"Detail Konfigurasi — {detail.title}")
        self.transient(parent)
        self.geometry("900x580")
        self.minsize(720, 480)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=14)
        for label, rows in detail.sections:
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=label)
            self._table(frame, rows)
        ttk.Button(self, text="Tutup", command=self.destroy).pack(pady=(0, 12))

    @staticmethod
    def _table(parent, rows) -> None:
        if not rows:
            ttk.Label(parent, text="Belum ada data konfigurasi.").pack(anchor="w")
            return
        columns = tuple(rows[0])
        table = ttk.Treeview(parent, columns=columns, show="headings")
        vertical = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for column in columns:
            table.heading(column, text=column.replace("_", " ").title())
            table.column(column, width=140, stretch=True)
        for row in rows:
            table.insert("", "end", values=tuple(row.get(column, "") for column in columns))
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
