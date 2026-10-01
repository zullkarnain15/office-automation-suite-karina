"""Structured configuration import preview dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ConfigurationImportPreviewDialog(tk.Toplevel):
    def __init__(self, parent, preview) -> None:
        super().__init__(parent)
        self.title("Preview Import Configuration")
        self.transient(parent)
        self.geometry("980x620")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=14)
        changes = ttk.Frame(notebook, padding=10)
        issues = ttk.Frame(notebook, padding=10)
        notebook.add(changes, text="Changes")
        notebook.add(issues, text="Issues")
        self._table(
            changes,
            ("module", "scope", "key", "operation", "old", "new", "destructive"),
            (
                "Module",
                "Scope",
                "Key",
                "Operation",
                "Old Value",
                "New Value",
                "Destructive",
            ),
            [
                (
                    item.module,
                    item.setting_scope,
                    item.setting_key,
                    item.operation.value,
                    self._short(item.old_value),
                    self._short(item.new_value),
                    "Ya" if item.destructive else "Tidak",
                )
                for item in preview.changes
            ],
        )
        self._table(
            issues,
            ("severity", "code", "module", "sheet", "field", "message"),
            ("Severity", "Code", "Module", "Sheet", "Field", "Message"),
            [
                (
                    item.severity.value,
                    item.code,
                    item.module,
                    item.sheet or "",
                    item.field or "",
                    item.message,
                )
                for item in preview.issues
            ],
        )

    @staticmethod
    def _short(value: object) -> str:
        text = "" if value is None else str(value)
        return text if len(text) <= 120 else text[:117] + "..."

    @staticmethod
    def _table(parent, columns, headings, rows) -> None:
        table = ttk.Treeview(parent, columns=columns, show="headings")
        for column, heading in zip(columns, headings, strict=True):
            table.heading(column, text=heading)
            table.column(column, width=130, stretch=True)
        for row in rows:
            table.insert("", "end", values=row)
        table.pack(fill="both", expand=True)
