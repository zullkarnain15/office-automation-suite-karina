"""Scrollable detail view for Attendance preflight validation."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from tkinter import ttk

from ui.attendance_models import AttendanceValidationResult


class AttendanceValidationDetailDialog(tk.Toplevel):
    """Show a large MDB validation result without truncating its source list."""

    def __init__(
        self,
        parent: tk.Misc,
        validation: AttendanceValidationResult | None,
        lines: tuple[str, ...],
    ) -> None:
        super().__init__(parent)
        self.title("Detail Validasi Attendance")
        self.transient(parent)
        self.geometry("980x640")
        self.minsize(760, 480)

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        self._add_summary(frame, validation, lines)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True, pady=(12, 0))
        sources = ttk.Frame(notebook, padding=10)
        messages = ttk.Frame(notebook, padding=10)
        notebook.add(sources, text="Daftar MDB")
        notebook.add(messages, text="Pesan Validasi")
        self._add_source_table(sources, validation)
        self._add_messages(messages, lines)

        ttk.Button(frame, text="Tutup", command=self.destroy).pack(
            anchor="e", pady=(12, 0)
        )

    @staticmethod
    def _add_summary(
        parent: ttk.Frame,
        validation: AttendanceValidationResult | None,
        lines: tuple[str, ...],
    ) -> None:
        summary = ttk.LabelFrame(parent, text="Ringkasan", padding=10)
        summary.pack(fill="x")
        if validation is None:
            ttk.Label(summary, text="Status: Perlu perhatian").pack(anchor="w")
            return

        statuses = Counter(source.status.upper() for source in validation.sources)
        status_parts = [f"MDB aktif: {len(validation.sources)}"]
        status_parts.extend(
            f"{status}: {count}" for status, count in sorted(statuses.items())
        )
        ttk.Label(
            summary,
            text=(
                f"Workflow: {validation.workflow}   |   "
                + "   |   ".join(status_parts)
            ),
        ).pack(anchor="w")
        ttk.Label(
            summary,
            text=(
                f"Peringatan: {len(validation.warnings)}   |   "
                f"Error: {len(validation.errors)}"
            ),
        ).pack(anchor="w", pady=(4, 0))

    @staticmethod
    def _add_source_table(
        parent: ttk.Frame,
        validation: AttendanceValidationResult | None,
    ) -> None:
        columns = ("status", "source", "path")
        table = ttk.Treeview(parent, columns=columns, show="headings")
        table.heading("status", text="Status")
        table.heading("source", text="Sumber MDB")
        table.heading("path", text="Lokasi MDB")
        table.column("status", width=100, stretch=False, anchor="center")
        table.column("source", width=220, stretch=True)
        table.column("path", width=580, stretch=True)

        vertical = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        if validation is not None:
            for source in validation.sources:
                table.insert(
                    "",
                    "end",
                    values=(source.status, source.name, str(source.mdb_path)),
                )
        if not table.get_children():
            table.insert("", "end", values=("-", "Belum ada sumber MDB", "-"))

        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

    @staticmethod
    def _add_messages(parent: ttk.Frame, lines: tuple[str, ...]) -> None:
        text = tk.Text(parent, wrap="word", height=12, padx=10, pady=8)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
