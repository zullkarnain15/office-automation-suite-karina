"""Tkinter GUI for Attachment Consolidation."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from config.app_config import OUTPUT_PATH, UTILITIES_ICON
from utilities.attachment_consolidation.engine import (
    AttachmentConsolidationEngine,
)
from utilities.attachment_consolidation.models import (
    MODE_EXCEL,
    MODE_TXT,
    ConsolidationCancelled,
    ConsolidationRequest,
    ConsolidationScan,
)


APP_BACKGROUND = "#EAF2FA"
APP_PANEL = "#F8FBFF"
APP_INPUT = "#F4F7FB"
APP_BORDER = "#C7D5E6"
APP_TEXT = "#102A43"
APP_MUTED = "#60758A"
APP_PRIMARY = "#123B63"
APP_ACCENT = "#198FA3"
APP_SUCCESS = "#43A58F"
APP_WARNING = "#B45309"
APP_LOG_BG = "#24384C"
APP_LOG_FG = "#F4F7FB"
DEFAULT_FONT = ("Segoe UI", 9)
BUTTON_FONT = ("Segoe UI", 9, "bold")
SECTION_FONT = ("Segoe UI", 11, "bold")


class AttachmentConsolidationGUI:
    """Thread-safe operator interface for manual attachment recovery."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.root.title("Attachment Consolidation")
        self.root.geometry("1180x720")
        self.root.minsize(1000, 650)
        self.root.configure(bg=APP_BACKGROUND)
        try:
            self.root.iconbitmap(UTILITIES_ICON)
        except Exception:
            pass

        self.mode_var = tk.StringVar(value=MODE_EXCEL)
        self.workflow_var = tk.StringVar(value="HO")
        self.source_root_var = tk.StringVar()
        self.output_root_var = tk.StringVar(value=str(OUTPUT_PATH))
        self.recursive_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(
            value="Ready. Pilih Source Root lalu jalankan Scan Files."
        )
        self.summary_vars = {
            key: tk.StringVar(value="0")
            for key in (
                "found",
                "ready",
                "skipped",
                "valid",
                "invalid",
                "output",
            )
        }
        self.engine = AttachmentConsolidationEngine()
        self.scan_result: ConsolidationScan | None = None
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._busy_action = ""

        self._configure_style()
        self._build()
        self._bind_inputs()
        self._refresh_controls()
        self.root.after(100, self._drain_events)

    def _build(self) -> None:
        tk.Label(
            self.root,
            text="Attachment Consolidation",
            font=("Segoe UI", 21, "bold"),
            bg=APP_BACKGROUND,
            fg=APP_PRIMARY,
        ).pack(pady=(9, 0))
        tk.Label(
            self.root,
            text=(
                "Recovery attachment Excel/TXT menjadi output HRIS "
                "tanpa mengubah file sumber"
            ),
            font=("Segoe UI", 10),
            bg=APP_BACKGROUND,
            fg=APP_MUTED,
        ).pack(pady=(0, 8))

        inputs = tk.LabelFrame(
            self.root,
            text="Consolidation Input",
            font=SECTION_FONT,
            bg=APP_PANEL,
            fg=APP_PRIMARY,
            padx=10,
            pady=7,
        )
        inputs.pack(fill="x", padx=16, pady=(0, 6))
        inputs.columnconfigure(1, weight=1)

        tk.Label(inputs, text="Mode", bg=APP_PANEL).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            inputs,
            textvariable=self.mode_var,
            values=(MODE_EXCEL, MODE_TXT),
            state="readonly",
            width=32,
        ).grid(row=0, column=1, sticky="w", padx=(8, 22), pady=2)
        tk.Label(inputs, text="Workflow", bg=APP_PANEL).grid(
            row=0, column=2, sticky="w"
        )
        workflow = tk.Frame(inputs, bg=APP_PANEL)
        workflow.grid(row=0, column=3, sticky="w", padx=(8, 0))
        for value in ("HO", "Branch"):
            tk.Radiobutton(
                workflow,
                text=value,
                value=value,
                variable=self.workflow_var,
                bg=APP_PANEL,
                activebackground=APP_PANEL,
            ).pack(side="left", padx=(0, 14))

        self._folder_row(inputs, 1, "Source Root", self.source_root_var)
        tk.Checkbutton(
            inputs,
            text="Scan Subfolders",
            variable=self.recursive_var,
            bg=APP_PANEL,
            activebackground=APP_PANEL,
        ).grid(row=2, column=1, sticky="w", padx=(7, 0), pady=1)
        self._folder_row(inputs, 3, "Output Root", self.output_root_var)
        tk.Label(
            inputs,
            text=(
                "Nama output otomatis • konfigurasi TXT_Max_Lines memakai "
                "Outlook Configuration"
            ),
            bg=APP_PANEL,
            fg=APP_MUTED,
            font=("Segoe UI", 8),
        ).grid(row=4, column=1, columnspan=3, sticky="w", padx=(7, 0))

        actions = tk.Frame(self.root, bg=APP_BACKGROUND)
        actions.pack(fill="x", padx=16, pady=(0, 6))
        self.scan_button = self._button(
            actions, "Scan Files", self._start_scan, APP_ACCENT
        )
        self.process_button = self._button(
            actions, "Process", self._start_process, APP_SUCCESS
        )
        self.cancel_button = self._button(
            actions, "Cancel", self._cancel, APP_WARNING
        )
        self.progress = ttk.Progressbar(
            actions,
            mode="determinate",
            maximum=100,
            style="Consolidation.Horizontal.TProgressbar",
        )
        self.progress.pack(
            side="right", fill="x", expand=True, padx=(20, 0)
        )

        preview = tk.LabelFrame(
            self.root,
            text="File Preview",
            font=SECTION_FONT,
            bg=APP_PANEL,
            fg=APP_PRIMARY,
            padx=7,
            pady=5,
        )
        # Keep the inventory compact. The Treeview remains fully usable through
        # its scrollbars, while the process log below receives the flexible
        # vertical space and stays visible on 720/768 px screens.
        preview.pack(fill="x", expand=False, padx=16, pady=(0, 6))
        columns = (
            "file",
            "type",
            "status",
            "size",
            "valid",
            "invalid",
            "path",
        )
        self.tree = ttk.Treeview(
            preview,
            columns=columns,
            show="headings",
            height=5,
        )
        headings = {
            "file": "File",
            "type": "Type",
            "status": "Status",
            "size": "Size KB",
            "valid": "Valid",
            "invalid": "Invalid",
            "path": "Relative Path",
        }
        widths = {
            "file": 180,
            "type": 60,
            "status": 145,
            "size": 80,
            "valid": 65,
            "invalid": 65,
            "path": 380,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                anchor="w" if column in {"file", "status", "path"} else "center",
            )
        vertical = ttk.Scrollbar(
            preview, orient="vertical", command=self.tree.yview
        )
        horizontal = ttk.Scrollbar(
            preview, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1)

        summary = tk.LabelFrame(
            self.root,
            text="Summary",
            font=SECTION_FONT,
            bg=APP_PANEL,
            fg=APP_PRIMARY,
            padx=8,
            pady=4,
        )
        summary.pack(fill="x", padx=16, pady=(0, 6))
        labels = (
            ("Files", "found"),
            ("Ready", "ready"),
            ("Skipped", "skipped"),
            ("Valid Rows", "valid"),
            ("Invalid Rows", "invalid"),
            ("TXT Output", "output"),
        )
        for column, (label, key) in enumerate(labels):
            cell = tk.Frame(summary, bg=APP_PANEL)
            cell.grid(row=0, column=column, sticky="ew", padx=8)
            tk.Label(
                cell, text=label + ":", bg=APP_PANEL, fg=APP_MUTED
            ).pack(side="left")
            tk.Label(
                cell,
                textvariable=self.summary_vars[key],
                bg=APP_PANEL,
                fg=APP_TEXT,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(4, 0))
            summary.columnconfigure(column, weight=1)

        log_frame = tk.LabelFrame(
            self.root,
            text="Process Log",
            font=SECTION_FONT,
            bg=APP_PANEL,
            fg=APP_PRIMARY,
            padx=7,
            pady=5,
        )
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.log_text = ScrolledText(
            log_frame,
            height=8,
            font=("Consolas", 9),
            bg=APP_LOG_BG,
            fg=APP_LOG_FG,
            state="disabled",
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)

        tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg=APP_PRIMARY,
            fg="white",
            font=DEFAULT_FONT,
            padx=10,
        ).pack(fill="x", side="bottom")

    def _folder_row(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        tk.Label(parent, text=label, bg=APP_PANEL).grid(
            row=row, column=0, sticky="w", pady=2
        )
        tk.Entry(
            parent,
            textvariable=variable,
            font=DEFAULT_FONT,
            bg=APP_INPUT,
            relief="solid",
            bd=1,
        ).grid(
            row=row,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(7, 8),
            pady=2,
            ipady=2,
        )
        tk.Button(
            parent,
            text="Browse",
            font=BUTTON_FONT,
            command=lambda: self._browse(variable),
        ).grid(row=row, column=4, sticky="e", pady=2)

    def _button(self, parent, text, command, color):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=BUTTON_FONT,
            bg=color,
            fg="white",
            activebackground=APP_PRIMARY,
            activeforeground="white",
            relief="flat",
            bd=0,
        )
        button.pack(side="left", padx=(0, 7), ipadx=8, ipady=4)
        return button

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Consolidation.Horizontal.TProgressbar",
            troughcolor=APP_BORDER,
            background=APP_SUCCESS,
            lightcolor=APP_SUCCESS,
            darkcolor=APP_SUCCESS,
            bordercolor=APP_BORDER,
            thickness=14,
        )

    def _bind_inputs(self) -> None:
        for variable in (
            self.mode_var,
            self.workflow_var,
            self.source_root_var,
            self.output_root_var,
            self.recursive_var,
        ):
            variable.trace_add("write", self._inputs_changed)

    def _inputs_changed(self, *_args: object) -> None:
        if self.scan_result is not None:
            self.scan_result = None
            self._append_log("Input berubah; hasil scan sebelumnya tidak berlaku.")
            self._clear_tree()
        self._refresh_controls()

    def _browse(self, variable: tk.StringVar) -> None:
        folder = filedialog.askdirectory(parent=self.root)
        if folder:
            variable.set(folder)

    def _request(self) -> ConsolidationRequest:
        return ConsolidationRequest(
            mode=self.mode_var.get(),
            workflow=self.workflow_var.get(),
            source_root=Path(self.source_root_var.get().strip()),
            output_root=Path(self.output_root_var.get().strip()),
            scan_subfolders=self.recursive_var.get(),
        )

    def _start_scan(self) -> None:
        self.scan_result = None
        self._clear_tree()
        self._start_worker("scan")

    def _start_process(self) -> None:
        if self.scan_result is None:
            return
        if self.scan_result.request_fingerprint != self._request().fingerprint():
            self.scan_result = None
            self._refresh_controls()
            messagebox.showwarning(
                "Attachment Consolidation",
                "Input berubah. Jalankan Scan Files kembali.",
                parent=self.root,
            )
            return
        self._start_worker("process")

    def _start_worker(self, action: str) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.cancel_event = threading.Event()
        self._busy_action = action
        self.progress["value"] = 0
        self.status_var.set(
            "Scanning files..."
            if action == "scan"
            else "Processing attachments..."
        )
        self._append_log(self.status_var.get())
        self._refresh_controls()
        request = self._request()
        self.worker = threading.Thread(
            target=self._worker,
            args=(action, request, self.scan_result),
            daemon=True,
        )
        self.worker.start()

    def _worker(
        self,
        action: str,
        request: ConsolidationRequest,
        scan: ConsolidationScan | None,
    ) -> None:
        try:
            if action == "scan":
                result = self.engine.scan(
                    request,
                    self.cancel_event,
                    self._progress_event,
                )
            else:
                result = self.engine.run(
                    request,
                    scan=scan,
                    cancel_event=self.cancel_event,
                    progress=self._progress_event,
                )
            self.event_queue.put((action + "_success", result))
        except ConsolidationCancelled as error:
            self.event_queue.put(("cancelled", str(error)))
        except Exception as error:
            self.event_queue.put(("error", error))

    def _progress_event(
        self,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        self.event_queue.put(
            ("progress", (stage, current, total, message))
        )

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set(
            "Cancellation requested; menunggu checkpoint yang aman..."
        )
        self._append_log(self.status_var.get())

    def _drain_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                self._handle_event(event, payload)
        except queue.Empty:
            pass
        try:
            if self.root.winfo_exists():
                self.root.after(100, self._drain_events)
        except tk.TclError:
            pass

    def _handle_event(self, event: str, payload: Any) -> None:
        if event == "progress":
            _stage, current, total, message = payload
            self.progress["value"] = (
                0 if not total else min(100, (current / total) * 100)
            )
            self.status_var.set(message)
            self._append_log(message)
            return

        self._busy_action = ""
        if event == "scan_success":
            self.scan_result = payload
            self._show_scan(payload)
            self.status_var.set(
                "Scan selesai. Process siap dijalankan."
                if payload.processable_files
                else "Scan selesai tetapi tidak ada file yang dapat diproses."
            )
        elif event == "process_success":
            self._show_result(payload)
            if payload.success:
                self.status_var.set("Attachment Consolidation selesai.")
                messagebox.showinfo(
                    "Attachment Consolidation",
                    "Proses selesai.\n\n"
                    f"Output: {payload.artifacts.job_folder}",
                    parent=self.root,
                )
            elif payload.cancelled:
                self.status_var.set("Proses dibatalkan dengan aman.")
            else:
                self.status_var.set("Proses gagal. Periksa report dan log.")
                messagebox.showerror(
                    "Attachment Consolidation",
                    payload.error_message,
                    parent=self.root,
                )
        elif event == "cancelled":
            self.status_var.set("Proses dibatalkan.")
            self._append_log(str(payload))
        else:
            self.status_var.set("Proses gagal.")
            self._append_log(f"ERROR: {payload}")
            messagebox.showerror(
                "Attachment Consolidation",
                str(payload),
                parent=self.root,
            )
        self._refresh_controls()

    def _show_scan(self, scan: ConsolidationScan) -> None:
        self._clear_tree()
        for item in scan.files:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.path.name,
                    item.extension,
                    item.status,
                    f"{item.size_bytes / 1024:.1f}",
                    "",
                    "",
                    item.relative_path,
                ),
            )
        found = len(scan.files)
        ready = len(scan.processable_files)
        self.summary_vars["found"].set(str(found))
        self.summary_vars["ready"].set(str(ready))
        self.summary_vars["skipped"].set(str(found - ready))
        for warning in scan.warnings:
            self._append_log("WARNING: " + warning)

    def _show_result(self, result: Any) -> None:
        self._clear_tree()
        for item in result.file_results:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.scanned.path.name,
                    item.scanned.extension,
                    item.status,
                    f"{item.scanned.size_bytes / 1024:.1f}",
                    item.valid_count,
                    item.invalid_count,
                    item.scanned.relative_path,
                ),
            )
        self.summary_vars["valid"].set(str(len(result.records)))
        self.summary_vars["invalid"].set(str(len(result.anomalies)))
        self.summary_vars["output"].set(str(len(result.output_files)))
        self._append_log(f"Report: {result.artifacts.report_file}")
        self._append_log(f"Summary: {result.artifacts.summary_json}")

    def _clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _inputs_complete(self) -> bool:
        if self.mode_var.get() not in {MODE_EXCEL, MODE_TXT}:
            return False
        if self.workflow_var.get() not in {"HO", "Branch"}:
            return False
        if not self.source_root_var.get().strip():
            return False
        if not self.output_root_var.get().strip():
            return False
        return Path(self.source_root_var.get().strip()).is_dir()

    def _refresh_controls(self) -> None:
        busy = bool(self._busy_action)
        self.scan_button.config(
            state="normal"
            if self._inputs_complete() and not busy
            else "disabled"
        )
        self.process_button.config(
            state="normal"
            if self.scan_result is not None
            and bool(self.scan_result.processable_files)
            and not busy
            else "disabled"
        )
        self.cancel_button.config(
            state="normal" if busy else "disabled"
        )

    def _append_log(self, message: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
