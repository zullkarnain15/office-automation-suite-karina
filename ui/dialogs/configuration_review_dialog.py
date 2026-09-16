"""User-oriented import review with technical detail available on demand."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ConfigurationReviewDialog(tk.Toplevel):
    def __init__(self, parent, preview, summary) -> None:
        super().__init__(parent)
        self.title("Hasil Pemeriksaan Konfigurasi")
        self.transient(parent)
        self.geometry("920x600")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=14)
        overview = ttk.Frame(notebook, padding=12)
        issues = ttk.Frame(notebook, padding=10)
        changes = ttk.Frame(notebook, padding=10)
        notebook.add(overview, text="Ringkasan")
        notebook.add(issues, text="Peringatan & Error")
        notebook.add(changes, text="Detail Teknis")
        lines = [
            *(f"{module}: {status.value}" for module, status in summary.modules),
            "",
            f"Ditambahkan: {summary.insert_count}",
            f"Diperbarui: {summary.update_count}",
            f"Dihapus: {summary.delete_count}",
            f"Peringatan: {summary.warning_count}",
            f"Error: {summary.error_count}",
            "Perlu Persetujuan: " + ("Ya" if summary.confirmation_required else "Tidak"),
        ]
        ttk.Label(overview, text="\n".join(lines), justify="left").pack(anchor="w")
        issue_rows = tuple(
            (item.severity, item.title, item.detail, item.technical_code)
            for item in summary.issues
        )
        self._table(issues, ("severity", "title", "detail", "code"), ("Status", "Pesan", "Tindakan", "Kode Teknis"), issue_rows)
        change_rows = tuple(
            (item.module, item.setting_scope, item.setting_key, item.operation.value, item.old_value or "", item.new_value or "", "Ya" if item.destructive else "Tidak")
            for item in preview.changes
        )
        self._table(changes, ("module", "scope", "key", "operation", "old", "new", "delete"), ("Modul", "Bagian", "Kunci", "Perubahan", "Nilai Aktif", "Nilai File", "Diganti/Dihapus"), change_rows)

    @staticmethod
    def _table(parent, columns, headings, rows) -> None:
        table = ttk.Treeview(parent, columns=columns, show="headings")
        vertical = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for column, heading in zip(columns, headings, strict=True):
            table.heading(column, text=heading)
            table.column(column, width=140, stretch=True)
        for row in rows:
            table.insert("", "end", values=row)
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
