"""Tkinter GUI for Comparison-Attendance Reconciliation."""

from __future__ import annotations

import calendar
import queue
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from config.app_config import DATE_FORMAT, OUTPUT_PATH, UTILITIES_ICON
from utilities.attendance_reconciliation.engine import ReconciliationEngine
from utilities.attendance_reconciliation.models import ReconciliationCancelled
from utilities.attendance_reconciliation.models import ReconciliationRequest
from utilities.attendance_reconciliation.models import ReconciliationScan
from utilities.attendance_reconciliation.models import SOURCE_MODE_JOB
from utilities.attendance_reconciliation.models import SOURCE_MODE_SCAN


APP_BACKGROUND = "#EAF2FA"
APP_PANEL = "#F8FBFF"
APP_INPUT = "#F4F7FB"
APP_BORDER = "#C7D5E6"
APP_TEXT = "#102A43"
APP_MUTED = "#60758A"
APP_ACCENT = "#198FA3"
APP_ACCENT_HOVER = "#123B63"
APP_SUCCESS = "#43A58F"
APP_WARNING = "#B45309"
APP_LOG_BG = "#24384C"
APP_LOG_FG = "#F4F7FB"
TITLE_FONT = ("Segoe UI", 21, "bold")
SECTION_FONT = ("Segoe UI", 11, "bold")
DEFAULT_FONT = ("Segoe UI", 9)
BUTTON_FONT = ("Segoe UI", 9, "bold")


class AttendanceReconciliationGUI:
    """Lightweight, thread-safe reconciliation interface."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.root.title("Comparison-Attendance Reconciliation")
        self.root.geometry("1180x760")
        self.root.minsize(1050, 700)
        self.root.configure(bg=APP_BACKGROUND)
        try:
            self.root.iconbitmap(UTILITIES_ICON)
        except Exception:
            pass

        today = date.today()
        self.source_mode_var = tk.StringVar(value=SOURCE_MODE_SCAN)
        self.workflow_var = tk.StringVar(value="HO")
        self.attendance_path_var = tk.StringVar(
            value=str(OUTPUT_PATH / "Attendance")
        )
        self.outlook_path_var = tk.StringVar(
            value=str(OUTPUT_PATH / "Outlook-Revisi")
        )
        self.start_date_var = tk.StringVar(
            value=today.replace(day=1).strftime(DATE_FORMAT)
        )
        self.end_date_var = tk.StringVar(value=today.strftime(DATE_FORMAT))
        self.output_path_var = tk.StringVar(value=str(OUTPUT_PATH))
        self.status_var = tk.StringVar(value="Ready. Complete the inputs, then scan.")
        self.summary_vars = {
            key: tk.StringVar(value="0" if key != "period" else "-")
            for key in (
                "attendance_found", "attendance_used", "attendance_skipped",
                "outlook_found", "outlook_used", "outlook_skipped",
                "warnings", "period", "workflow",
            )
        }
        self.engine = ReconciliationEngine()
        self.scan_result: ReconciliationScan | None = None
        self.cancel_event = threading.Event()
        self.event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self._busy_action = ""
        self._build_widgets()
        self._configure_style()
        self._bind_input_changes()
        self._refresh_controls()
        self.root.after(100, self._drain_worker_events)

    def _build_widgets(self) -> None:
        tk.Label(
            self.root,
            text="Comparison-Attendance Reconciliation",
            font=TITLE_FONT,
            bg=APP_BACKGROUND,
            fg=APP_ACCENT_HOVER,
        ).pack(pady=(8, 0))
        tk.Label(
            self.root,
            text="Membandingkan data Attendance mesin dengan data revisi Outlook",
            font=("Segoe UI", 10),
            bg=APP_BACKGROUND,
            fg=APP_MUTED,
        ).pack(pady=(0, 7))

        input_frame = tk.LabelFrame(
            self.root, text="Comparison Input", font=SECTION_FONT,
            bg=APP_PANEL, fg=APP_ACCENT_HOVER, padx=10, pady=7,
        )
        input_frame.pack(fill="x", padx=16, pady=(0, 6))
        for column in (1, 4):
            input_frame.columnconfigure(column, weight=1)

        tk.Label(input_frame, text="Source Mode", bg=APP_PANEL).grid(
            row=0, column=0, sticky="w"
        )
        mode = ttk.Combobox(
            input_frame,
            textvariable=self.source_mode_var,
            state="readonly",
            values=(SOURCE_MODE_SCAN, SOURCE_MODE_JOB),
            width=31,
        )
        mode.grid(row=0, column=1, sticky="ew", padx=(6, 14), pady=2)
        tk.Label(input_frame, text="Workflow", bg=APP_PANEL).grid(
            row=0, column=3, sticky="w"
        )
        workflow_frame = tk.Frame(input_frame, bg=APP_PANEL)
        workflow_frame.grid(row=0, column=4, sticky="w", padx=(6, 0))
        for value in ("HO", "Branch"):
            tk.Radiobutton(
                workflow_frame, text=value, value=value,
                variable=self.workflow_var, bg=APP_PANEL,
                activebackground=APP_PANEL,
            ).pack(side="left", padx=(0, 12))

        self._folder_row(
            input_frame, 1, "Attendance Output Root / Job Folder",
            self.attendance_path_var,
        )
        self._folder_row(
            input_frame, 2, "Outlook-Revisi Output Root / Job Folder",
            self.outlook_path_var,
        )
        self._folder_row(
            input_frame, 3, "Output Folder", self.output_path_var
        )

        tk.Label(input_frame, text="Start Date (MM/DD/YYYY)", bg=APP_PANEL).grid(
            row=4, column=0, sticky="w", pady=(3, 0)
        )
        tk.Entry(
            input_frame, textvariable=self.start_date_var,
            font=DEFAULT_FONT, bg=APP_INPUT, relief="solid", bd=1,
        ).grid(row=4, column=1, sticky="ew", padx=(6, 14), pady=(3, 0), ipady=2)
        tk.Button(
            input_frame, text="Calendar", font=BUTTON_FONT,
            command=lambda: self._open_date_picker(self.start_date_var),
            bg=APP_ACCENT, fg="white",
            activebackground=APP_ACCENT_HOVER, activeforeground="white",
            relief="flat", bd=0,
        ).grid(row=4, column=2, sticky="w", pady=(3, 0))
        tk.Label(input_frame, text="End Date (MM/DD/YYYY)", bg=APP_PANEL).grid(
            row=4, column=3, sticky="w", pady=(3, 0)
        )
        tk.Entry(
            input_frame, textvariable=self.end_date_var,
            font=DEFAULT_FONT, bg=APP_INPUT, relief="solid", bd=1,
        ).grid(row=4, column=4, sticky="ew", padx=(6, 0), pady=(3, 0), ipady=2)
        tk.Button(
            input_frame, text="Calendar", font=BUTTON_FONT,
            command=lambda: self._open_date_picker(self.end_date_var),
            bg=APP_ACCENT, fg="white",
            activebackground=APP_ACCENT_HOVER, activeforeground="white",
            relief="flat", bd=0,
        ).grid(row=4, column=5, sticky="e", padx=(8, 0), pady=(3, 0))

        action_frame = tk.Frame(self.root, bg=APP_BACKGROUND)
        action_frame.pack(fill="x", padx=16, pady=(0, 6))
        self.scan_button = self._button(
            action_frame, "Scan Reports", self._start_scan, APP_ACCENT
        )
        self.cancel_scan_button = self._button(
            action_frame, "Cancel Scan", self._cancel, APP_WARNING
        )
        self.run_button = self._button(
            action_frame, "Run Comparison", self._start_comparison, APP_SUCCESS
        )
        self.cancel_run_button = self._button(
            action_frame, "Cancel Comparison", self._cancel, APP_WARNING
        )
        self.progress = ttk.Progressbar(
            action_frame,
            mode="indeterminate",
            style="Reconciliation.Green.Horizontal.TProgressbar",
        )
        self.progress.pack(side="right", fill="x", expand=True, padx=(20, 0))

        middle = tk.Frame(self.root, bg=APP_BACKGROUND)
        middle.pack(fill="x", padx=16, pady=(0, 6))
        summary_frame = tk.LabelFrame(
            middle, text="Scan Summary", font=SECTION_FONT,
            bg=APP_PANEL, fg=APP_ACCENT_HOVER, padx=8, pady=5,
        )
        summary_frame.pack(fill="x")
        labels = (
            ("Attendance Reports Found", "attendance_found"),
            ("Attendance Reports Used", "attendance_used"),
            ("Attendance Reports Skipped", "attendance_skipped"),
            ("Outlook Reports Found", "outlook_found"),
            ("Outlook Reports Used", "outlook_used"),
            ("Outlook Reports Skipped", "outlook_skipped"),
            ("Warnings", "warnings"),
            ("Selected Period", "period"),
            ("Workflow", "workflow"),
        )
        for index, (label, key) in enumerate(labels):
            row, column = divmod(index, 3)
            cell = tk.Frame(summary_frame, bg=APP_PANEL)
            cell.grid(row=row, column=column, sticky="ew", padx=7, pady=2)
            tk.Label(cell, text=label + ":", bg=APP_PANEL, fg=APP_MUTED).pack(
                side="left"
            )
            tk.Label(
                cell, textvariable=self.summary_vars[key], bg=APP_PANEL,
                fg=APP_TEXT, font=("Segoe UI", 9, "bold"),
            ).pack(side="left", padx=(5, 0))
            summary_frame.columnconfigure(column, weight=1)

        log_frame = tk.LabelFrame(
            self.root, text="Process Log", font=SECTION_FONT,
            bg=APP_PANEL, fg=APP_ACCENT_HOVER, padx=8, pady=5,
        )
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))
        self.log_text = ScrolledText(
            log_frame, height=10, font=("Consolas", 9),
            bg=APP_LOG_BG, fg=APP_LOG_FG, state="disabled", wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)
        tk.Label(
            self.root, textvariable=self.status_var, anchor="w",
            bg=APP_ACCENT_HOVER, fg="white", font=DEFAULT_FONT, padx=10,
        ).pack(fill="x", side="bottom")

    def _folder_row(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        tk.Label(parent, text=label, bg=APP_PANEL).grid(
            row=row, column=0, columnspan=1, sticky="w", pady=2
        )
        tk.Entry(
            parent, textvariable=variable, font=DEFAULT_FONT,
            bg=APP_INPUT, relief="solid", bd=1,
        ).grid(
            row=row, column=1, columnspan=4, sticky="ew",
            padx=(6, 8), pady=2, ipady=2,
        )
        tk.Button(
            parent, text="Browse", font=BUTTON_FONT,
            command=lambda selected=variable: self._browse(selected),
        ).grid(row=row, column=5, sticky="e", pady=2)

    def _button(self, parent, text, command, color):
        button = tk.Button(
            parent, text=text, command=command, font=BUTTON_FONT,
            bg=color, fg="white", activebackground=APP_ACCENT_HOVER,
            activeforeground="white", relief="flat", bd=0,
        )
        button.pack(side="left", padx=(0, 7), ipady=4, ipadx=7)
        return button

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Reconciliation.Green.Horizontal.TProgressbar",
            troughcolor=APP_BORDER,
            background=APP_SUCCESS,
            lightcolor=APP_SUCCESS,
            darkcolor=APP_SUCCESS,
            bordercolor=APP_BORDER,
            thickness=14,
        )

    def _bind_input_changes(self) -> None:
        for variable in (
            self.source_mode_var, self.workflow_var, self.attendance_path_var,
            self.outlook_path_var, self.start_date_var, self.end_date_var,
            self.output_path_var,
        ):
            variable.trace_add("write", self._inputs_changed)

    def _inputs_changed(self, *_args: object) -> None:
        if self.scan_result is not None:
            self.scan_result = None
            self._append_log("Input changed; previous scan is stale.")
        self._refresh_controls()

    def _browse(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(parent=self.root)
        if selected:
            variable.set(selected)

    def _open_date_picker(self, target: tk.StringVar) -> None:
        """Open the same lightweight calendar pattern used by core modules."""
        try:
            initial = datetime.strptime(target.get().strip(), DATE_FORMAT).date()
        except ValueError:
            initial = date.today()

        picker = tk.Toplevel(self.root)
        picker.title("Select Date")
        picker.geometry("330x305")
        picker.resizable(False, False)
        picker.transient(self.root)
        picker.grab_set()
        selected_year = tk.IntVar(value=initial.year)
        selected_month = tk.IntVar(value=initial.month)
        header = tk.Frame(picker)
        header.pack(fill="x", pady=8)
        calendar_frame = tk.Frame(picker)
        calendar_frame.pack(pady=5)
        title = tk.Label(header, text="", font=SECTION_FONT)
        title.pack(side="left", expand=True)

        def refresh() -> None:
            for widget in calendar_frame.winfo_children():
                widget.destroy()
            title.config(
                text=f"{calendar.month_name[selected_month.get()]} "
                f"{selected_year.get()}"
            )
            for column, day_name in enumerate(
                ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            ):
                tk.Label(
                    calendar_frame, text=day_name, width=4, font=DEFAULT_FONT
                ).grid(row=0, column=column, padx=2, pady=2)
            for row_index, week in enumerate(
                calendar.monthcalendar(
                    selected_year.get(), selected_month.get()
                ),
                1,
            ):
                for column, day_number in enumerate(week):
                    if not day_number:
                        tk.Label(calendar_frame, text="", width=4).grid(
                            row=row_index, column=column, padx=2, pady=2
                        )
                        continue
                    tk.Button(
                        calendar_frame,
                        text=str(day_number),
                        width=4,
                        command=lambda day_value=day_number: select(day_value),
                    ).grid(row=row_index, column=column, padx=2, pady=2)

        def move_month(offset: int) -> None:
            month = selected_month.get() + offset
            year = selected_year.get()
            if month == 0:
                month, year = 12, year - 1
            elif month == 13:
                month, year = 1, year + 1
            selected_month.set(month)
            selected_year.set(year)
            refresh()

        def select(day_number: int) -> None:
            selected = date(
                selected_year.get(), selected_month.get(), day_number
            )
            target.set(selected.strftime(DATE_FORMAT))
            picker.destroy()

        tk.Button(
            header, text="<", width=4, command=lambda: move_month(-1)
        ).pack(side="left", padx=10)
        tk.Button(
            header, text=">", width=4, command=lambda: move_month(1)
        ).pack(side="right", padx=10)
        refresh()

    def _request(self) -> ReconciliationRequest:
        try:
            start_date = datetime.strptime(
                self.start_date_var.get().strip(), DATE_FORMAT
            ).date()
            end_date = datetime.strptime(
                self.end_date_var.get().strip(), DATE_FORMAT
            ).date()
        except ValueError as error:
            raise ValueError("Start Date and End Date must use MM/DD/YYYY.") from error
        return ReconciliationRequest(
            source_mode=self.source_mode_var.get(),
            workflow=self.workflow_var.get(),
            attendance_path=Path(self.attendance_path_var.get().strip()),
            outlook_path=Path(self.outlook_path_var.get().strip()),
            start_date=start_date,
            end_date=end_date,
            output_folder=Path(self.output_path_var.get().strip()),
        )

    def _inputs_look_complete(self) -> bool:
        if self.workflow_var.get() not in {"HO", "Branch"}:
            return False
        if not all(
            value.get().strip()
            for value in (
                self.attendance_path_var, self.outlook_path_var,
                self.start_date_var, self.end_date_var, self.output_path_var,
            )
        ):
            return False
        try:
            request = self._request()
        except ValueError:
            return False
        return (
            request.start_date <= request.end_date
            and request.attendance_path.is_dir()
            and request.outlook_path.is_dir()
        )

    def _start_scan(self) -> None:
        try:
            request = self._request()
        except ValueError as error:
            messagebox.showerror("Reconciliation", str(error), parent=self.root)
            return
        self.scan_result = None
        self._start_worker("scan", request)

    def _start_comparison(self) -> None:
        if self.scan_result is None:
            return
        try:
            request = self._request()
        except ValueError as error:
            messagebox.showerror("Reconciliation", str(error), parent=self.root)
            return
        if self.scan_result.fingerprint != request.fingerprint():
            self.scan_result = None
            self._refresh_controls()
            messagebox.showwarning(
                "Reconciliation", "Input changed. Scan Reports again.",
                parent=self.root,
            )
            return
        self._start_worker("comparison", request)

    def _start_worker(self, action: str, request: ReconciliationRequest) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.cancel_event = threading.Event()
        self._busy_action = action
        self.progress.start(12)
        self.status_var.set(
            "Scanning reports..." if action == "scan" else "Running comparison..."
        )
        self._append_log(self.status_var.get())
        self._refresh_controls()
        self.worker = threading.Thread(
            target=self._worker,
            args=(action, request, self.scan_result),
            daemon=True,
        )
        self.worker.start()

    def _worker(
        self,
        action: str,
        request: ReconciliationRequest,
        scan: ReconciliationScan | None,
    ) -> None:
        try:
            if action == "scan":
                result = self.engine.scan(request, self.cancel_event)
            else:
                result = self.engine.run(
                    request, scan=scan, cancel_event=self.cancel_event
                )
            self.event_queue.put((action + "_success", result))
        except ReconciliationCancelled as error:
            self.event_queue.put(("cancelled", str(error)))
        except Exception as error:
            self.event_queue.put(("error", error))

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Cancellation requested; waiting for a safe checkpoint...")
        self._append_log(self.status_var.get())

    def _drain_worker_events(self) -> None:
        try:
            while True:
                event, payload = self.event_queue.get_nowait()
                self._handle_worker_event(event, payload)
        except queue.Empty:
            pass
        try:
            if self.root.winfo_exists():
                self.root.after(100, self._drain_worker_events)
        except tk.TclError:
            pass

    def _handle_worker_event(self, event: str, payload: Any) -> None:
        self.progress.stop()
        self._busy_action = ""
        if event == "scan_success":
            self.scan_result = payload
            self._show_scan_summary(payload)
            self.status_var.set("Scan completed. Run Comparison is ready.")
            self._append_log(self.status_var.get())
        elif event == "comparison_success":
            self.status_var.set("Comparison completed successfully.")
            self._append_log(f"Report: {payload.report_file}")
            messagebox.showinfo(
                "Reconciliation",
                "Comparison completed.\n\n"
                f"Report: {payload.report_file}",
                parent=self.root,
            )
        elif event == "cancelled":
            self.status_var.set("Process cancelled safely.")
            self._append_log(str(payload))
        else:
            self.status_var.set("Process failed.")
            self._append_log(f"ERROR: {payload}")
            messagebox.showerror("Reconciliation", str(payload), parent=self.root)
        self._refresh_controls()

    def _show_scan_summary(self, scan: ReconciliationScan) -> None:
        values = {
            "attendance_found": scan.attendance.reports_found,
            "attendance_used": scan.attendance.reports_used,
            "attendance_skipped": scan.attendance.reports_skipped,
            "outlook_found": scan.outlook.reports_found,
            "outlook_used": scan.outlook.reports_used,
            "outlook_skipped": scan.outlook.reports_skipped,
            "warnings": len(scan.warnings),
            "period": f"{self.start_date_var.get()} - {self.end_date_var.get()}",
            "workflow": self.workflow_var.get(),
        }
        for key, value in values.items():
            self.summary_vars[key].set(str(value))
        for warning in scan.warnings:
            self._append_log("WARNING: " + warning)

    def _refresh_controls(self) -> None:
        busy = bool(self._busy_action)
        self.scan_button.config(
            state="normal" if self._inputs_look_complete() and not busy else "disabled"
        )
        self.run_button.config(
            state="normal" if self.scan_result is not None and not busy else "disabled"
        )
        self.cancel_scan_button.config(
            state="normal" if self._busy_action == "scan" else "disabled"
        )
        self.cancel_run_button.config(
            state="normal" if self._busy_action == "comparison" else "disabled"
        )

    def _append_log(self, message: str) -> None:
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
