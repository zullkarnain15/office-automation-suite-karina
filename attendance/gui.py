"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : gui.py
Module      : Attendance
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
Attendance GUI

This module contains user interface, light input validation,
date picker, and integration to Attendance Process Engine.

No attendance business logic is allowed here.

=========================================================
"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from attendance.engine import AttendanceProcessEngine
from config.app_config import ATTENDANCE_ICON
from config.app_config import DATE_FORMAT
from config.ui_config import BUTTON_FONT
from config.ui_config import DEFAULT_FONT
from config.ui_config import HEADER_FONT
from shared.config_manager import AttendanceConfigurationReader
from shared.dialogs import Dialog
from shared.logger import get_logger
from shared.validators import validate_extension
from shared.validators import validate_file
from shared.validators import validate_folder
from shared.validators import validate_required

logger = get_logger(__name__)

VS_CODE_BACKGROUND = "#1E1E1E"
VS_CODE_PANEL = "#252526"
VS_CODE_SURFACE = "#2D2D30"
VS_CODE_SURFACE_ACTIVE = "#3E3E42"
VS_CODE_INPUT = "#1B1B1B"
VS_CODE_BORDER = "#3C3C3C"
VS_CODE_TEXT = "#D4D4D4"
VS_CODE_MUTED_TEXT = "#9CDCFE"
VS_CODE_ACCENT = "#007ACC"
VS_CODE_ACCENT_HOVER = "#0E639C"
VS_CODE_SUCCESS = "#22C55E"
VS_CODE_SUCCESS_ACTIVE = "#16A34A"
VS_CODE_SUCCESS_BORDER = "#15803D"


class AttendanceGUI:
    """Attendance Module GUI."""

    def __init__(self, master: tk.Toplevel) -> None:
        self.master = master

        self.master.title("Attendance Module")
        self.master.geometry("900x650")
        self.master.minsize(850, 600)
        self.master.configure(bg=VS_CODE_BACKGROUND)

        try:
            self.master.iconbitmap(ATTENDANCE_ICON)
        except Exception:
            logger.warning("Attendance icon could not be loaded.")

        self.workflow_var = tk.StringVar(value="HO")
        self.use_config_output_var = tk.BooleanVar(value=True)
        self.generate_txt_var = tk.BooleanVar(value=True)
        self.generate_report_var = tk.BooleanVar(value=True)

        self._configure_ttk_style()
        self._create_widgets()
        self._apply_widget_theme(self.master)
        self._style_primary_action()

    # =====================================================
    # GUI
    # =====================================================

    def _create_widgets(self) -> None:
        header = tk.Label(
            self.master,
            text="Attendance Module",
            font=HEADER_FONT,
            bg=VS_CODE_BACKGROUND,
        )

        header.pack(pady=(8, 6))

        frame = tk.LabelFrame(
            self.master,
            text="Attendance Configuration",
            padx=12,
            pady=10,
        )

        frame.pack(
            fill="x",
            padx=15,
        )

        # CONFIGURATION FILE

        tk.Label(
            frame,
            text="Attendance Configuration (.xlsx)",
            font=DEFAULT_FONT,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=5,
        )

        self.config_entry = tk.Entry(
            frame,
            width=62,
        )

        self.config_entry.grid(
            row=0,
            column=1,
            padx=10,
            sticky="we",
        )

        tk.Button(
            frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self.browse_configuration,
        ).grid(
            row=0,
            column=2,
        )

        # OUTPUT FOLDER

        tk.Label(
            frame,
            text="Output Folder",
            font=DEFAULT_FONT,
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=5,
        )

        self.output_entry = tk.Entry(
            frame,
            width=62,
        )

        self.output_entry.grid(
            row=1,
            column=1,
            padx=10,
            sticky="we",
        )

        self.output_browse_button = tk.Button(
            frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self.browse_output,
        )

        self.output_browse_button.grid(
            row=1,
            column=2,
        )

        tk.Checkbutton(
            frame,
            text="Same as Configuration File",
            variable=self.use_config_output_var,
            font=DEFAULT_FONT,
            command=self.toggle_output_source,
        ).grid(
            row=2,
            column=1,
            sticky="w",
            padx=10,
            pady=(0, 5),
        )

        # DATE RANGE

        tk.Label(
            frame,
            text="Date Range",
            font=DEFAULT_FONT,
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=5,
        )

        date_frame = tk.Frame(
            frame,
        )

        date_frame.grid(
            row=3,
            column=1,
            sticky="w",
            padx=10,
            pady=5,
        )

        tk.Label(
            date_frame,
            text="From",
            font=DEFAULT_FONT,
        ).pack(side="left")

        self.date_from_entry = tk.Entry(
            date_frame,
            width=15,
        )

        self.date_from_entry.pack(
            side="left",
            padx=(5, 3),
        )

        tk.Button(
            date_frame,
            text="📅",
            width=3,
            command=lambda: self.open_date_picker("from"),
        ).pack(
            side="left",
            padx=(0, 15),
        )

        tk.Label(
            date_frame,
            text="To",
            font=DEFAULT_FONT,
        ).pack(side="left")

        self.date_to_entry = tk.Entry(
            date_frame,
            width=15,
        )

        self.date_to_entry.pack(
            side="left",
            padx=(5, 3),
        )

        tk.Button(
            date_frame,
            text="📅",
            width=3,
            command=lambda: self.open_date_picker("to"),
        ).pack(
            side="left",
            padx=(0, 15),
        )

        tk.Label(
            date_frame,
            text="Format: MM/DD/YYYY",
            font=DEFAULT_FONT,
        ).pack(side="left")

        frame.columnconfigure(1, weight=1)
        self.toggle_output_source()

        # =================================================
        # OPTIONS WRAPPER
        # =================================================

        option_wrapper = tk.Frame(
            self.master,
            bg=VS_CODE_BACKGROUND,
        )

        option_wrapper.pack(
            fill="x",
            padx=15,
            pady=(8, 0),
        )

        # WORKFLOW FRAME

        workflow_frame = tk.LabelFrame(
            option_wrapper,
            text="Workflow",
            padx=12,
            pady=8,
        )

        workflow_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 8),
        )

        tk.Radiobutton(
            workflow_frame,
            text="Head Office (HO)",
            variable=self.workflow_var,
            value="HO",
            font=DEFAULT_FONT,
            command=self.update_workflow_status,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
        )

        tk.Radiobutton(
            workflow_frame,
            text="Branch",
            variable=self.workflow_var,
            value="Branch",
            font=DEFAULT_FONT,
            command=self.update_workflow_status,
        ).grid(
            row=0,
            column=1,
            sticky="w",
            padx=20,
        )

        self.workflow_status_label = tk.Label(
            workflow_frame,
            text="Selected Workflow : Head Office (HO)",
            font=DEFAULT_FONT,
        )

        self.workflow_status_label.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=(6, 0),
        )

        # OUTPUT OPTIONS FRAME

        output_option_frame = tk.LabelFrame(
            option_wrapper,
            text="Output Options",
            padx=12,
            pady=8,
        )

        output_option_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(8, 0),
        )

        tk.Checkbutton(
            output_option_frame,
            text="Generate HRIS TXT",
            variable=self.generate_txt_var,
            font=DEFAULT_FONT,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
        )

        tk.Checkbutton(
            output_option_frame,
            text="Generate Excel Report",
            variable=self.generate_report_var,
            font=DEFAULT_FONT,
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=5,
            pady=(5, 0),
        )

        # =================================================
        # ACTION + PROGRESS
        # =================================================

        action_frame = tk.Frame(
            self.master,
            bg=VS_CODE_BACKGROUND,
        )

        action_frame.pack(
            fill="x",
            padx=15,
            pady=(10, 0),
        )

        self.generate_button = tk.Button(
            action_frame,
            text="Generate",
            width=18,
            font=BUTTON_FONT,
            command=self.generate,
        )

        self.generate_button.pack(
            side="left",
            padx=(0, 15),
        )

        progress_frame = tk.LabelFrame(
            action_frame,
            text="Progress",
            padx=8,
            pady=6,
        )

        progress_frame.pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.progress = ttk.Progressbar(
            progress_frame,
            length=500,
            mode="determinate",
            style="Attendance.Horizontal.TProgressbar",
        )

        self.progress.pack(
            fill="x",
        )

        # =================================================
        # PROCESS LOG
        # =================================================

        log_frame = tk.LabelFrame(
            self.master,
            text="Process Log",
            padx=10,
            pady=8,
        )

        log_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(10, 8),
        )

        self.log_text = ScrolledText(
            log_frame,
            height=12,
            wrap="word",
        )

        self.log_text.pack(
            fill="both",
            expand=True,
        )

        self.append_log("Application Ready.")
        self.append_log("Waiting for user input...")

        # STATUS BAR

        self.status_label = tk.Label(
            self.master,
            text="Status : Ready",
            anchor="w",
            relief="sunken",
        )

        self.status_label.pack(
            fill="x",
            side="bottom",
        )

    # =====================================================
    # EVENT
    # =====================================================

    def browse_configuration(self) -> None:
        """Browse Attendance Configuration workbook."""

        filename = filedialog.askopenfilename(
            title="Select Attendance Configuration",
            filetypes=[
                ("Excel Workbook", "*.xlsx"),
            ],
        )

        if filename:
            self.config_entry.delete(0, tk.END)
            self.config_entry.insert(0, filename)

            self.append_log("Attendance Configuration selected.")
            self.update_status("Configuration selected")

            if self.use_config_output_var.get():
                self.load_output_folder_from_configuration(
                    show_warning=True
                )

    def browse_output(self) -> None:
        """Browse output folder."""

        folder = filedialog.askdirectory(
            title="Select Output Folder"
        )

        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)

            self.append_log("Output folder selected.")
            self.update_status("Output folder selected")

    def toggle_output_source(self) -> None:
        """Toggle output folder source between config and manual."""

        if self.use_config_output_var.get():
            self.output_browse_button.config(state="disabled")
            self.output_entry.config(state="normal")
            self.load_output_folder_from_configuration(
                show_warning=False
            )
            self.output_entry.config(state="disabled")
            if hasattr(self, "log_text"):
                self.append_log(
                    "Output folder source: Attendance Configuration."
                )
        else:
            self.output_entry.config(state="normal")
            self.output_browse_button.config(state="normal")
            if hasattr(self, "log_text"):
                self.append_log("Output folder source: Manual selection.")

    def load_output_folder_from_configuration(
        self,
        show_warning: bool,
    ) -> bool:
        """Load output folder from selected Attendance Configuration."""

        config_file = self.config_entry.get().strip()

        if not config_file:
            return False

        try:
            configuration_reader = AttendanceConfigurationReader(
                config_file
            )
            configuration = configuration_reader.read()
            output_folder = configuration.get_output_folder()
        except Exception as exc:
            self.append_log(
                f"Failed to read output folder from configuration: {exc}"
            )

            if show_warning:
                Dialog.warning(
                    "Output Folder could not be read from "
                    "Attendance Configuration.\n\n"
                    f"{exc}"
                )

            return False

        if output_folder is None:
            self.append_log(
                "OutputFolder is not set in Attendance Configuration."
            )

            if show_warning:
                Dialog.warning(
                    "OutputFolder is not set in Attendance Configuration."
                )

            return False

        self.output_entry.config(state="normal")
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, str(output_folder))

        if self.use_config_output_var.get():
            self.output_entry.config(state="disabled")

        self.append_log(
            f"Output folder loaded from configuration: {output_folder}"
        )
        self.update_status("Output folder loaded from configuration")

        return True

    def update_workflow_status(self) -> None:
        """Update selected workflow information."""

        workflow = self.workflow_var.get()

        if workflow == "HO":
            text = "Selected Workflow : Head Office (HO)"
        else:
            text = "Selected Workflow : Branch"

        self.workflow_status_label.config(text=text)

        self.append_log(text)

    def generate(self) -> None:
        """Validate input and run Attendance Process Engine."""

        self.append_log("Generate button clicked.")
        self.update_status("Validating input")

        if not self.validate_input():
            return

        process_input = self.collect_input()

        self.append_log("Input validation success.")
        self.log_process_input(process_input)

        self.run_attendance_process(process_input)

    # =====================================================
    # DATE PICKER
    # =====================================================

    def open_date_picker(self, target: str) -> None:
        """Open simple calendar date picker."""

        initial_date = self._get_initial_picker_date(target)

        picker = tk.Toplevel(self.master)
        picker.title("Select Date")
        picker.geometry("320x300")
        picker.resizable(False, False)
        picker.transient(self.master)
        picker.grab_set()

        selected_year = tk.IntVar(value=initial_date.year)
        selected_month = tk.IntVar(value=initial_date.month)

        header_frame = tk.Frame(picker)
        header_frame.pack(fill="x", pady=8)

        calendar_frame = tk.Frame(picker)
        calendar_frame.pack(pady=5)

        def previous_month() -> None:
            month = selected_month.get()
            year = selected_year.get()

            if month == 1:
                selected_month.set(12)
                selected_year.set(year - 1)
            else:
                selected_month.set(month - 1)

            refresh_calendar()

        def next_month() -> None:
            month = selected_month.get()
            year = selected_year.get()

            if month == 12:
                selected_month.set(1)
                selected_year.set(year + 1)
            else:
                selected_month.set(month + 1)

            refresh_calendar()

        def select_date(day_number: int) -> None:
            selected_date = date(
                selected_year.get(),
                selected_month.get(),
                day_number,
            )

            formatted_date = selected_date.strftime(DATE_FORMAT)

            if target == "from":
                self.date_from_entry.delete(0, tk.END)
                self.date_from_entry.insert(0, formatted_date)
                self.append_log(f"Date From selected: {formatted_date}")
            else:
                self.date_to_entry.delete(0, tk.END)
                self.date_to_entry.insert(0, formatted_date)
                self.append_log(f"Date To selected: {formatted_date}")

            picker.destroy()

        def refresh_calendar() -> None:
            for widget in calendar_frame.winfo_children():
                widget.destroy()

            month_name = calendar.month_name[selected_month.get()]

            title_label.config(
                text=f"{month_name} {selected_year.get()}"
            )

            day_names = [
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
            ]

            for column_index, day_name in enumerate(day_names):
                tk.Label(
                    calendar_frame,
                    text=day_name,
                    width=4,
                    font=DEFAULT_FONT,
                ).grid(
                    row=0,
                    column=column_index,
                    padx=2,
                    pady=2,
                )

            month_calendar = calendar.monthcalendar(
                selected_year.get(),
                selected_month.get(),
            )

            for row_index, week in enumerate(
                month_calendar,
                start=1,
            ):
                for column_index, day_number in enumerate(week):
                    if day_number == 0:
                        tk.Label(
                            calendar_frame,
                            text="",
                            width=4,
                        ).grid(
                            row=row_index,
                            column=column_index,
                            padx=2,
                            pady=2,
                        )
                    else:
                        tk.Button(
                            calendar_frame,
                            text=str(day_number),
                            width=4,
                            command=lambda day=day_number: select_date(
                                day
                            ),
                        ).grid(
                            row=row_index,
                            column=column_index,
                            padx=2,
                            pady=2,
                        )

            self._apply_widget_theme(picker)

        tk.Button(
            header_frame,
            text="<",
            width=4,
            command=previous_month,
        ).pack(
            side="left",
            padx=10,
        )

        title_label = tk.Label(
            header_frame,
            text="",
            font=HEADER_FONT,
        )

        title_label.pack(
            side="left",
            expand=True,
        )

        tk.Button(
            header_frame,
            text=">",
            width=4,
            command=next_month,
        ).pack(
            side="right",
            padx=10,
        )

        refresh_calendar()

    def _get_initial_picker_date(self, target: str) -> date:
        """Return initial date for date picker."""

        if target == "from":
            value = self.date_from_entry.get().strip()
        else:
            value = self.date_to_entry.get().strip()

        try:
            parsed_date = datetime.strptime(
                value,
                DATE_FORMAT,
            )
            return parsed_date.date()
        except ValueError:
            return date.today()

    # =====================================================
    # ENGINE INTEGRATION
    # =====================================================

    def collect_input(self) -> dict[str, Any]:
        """
        Collect GUI input for Attendance Engine.

        This method is the integration boundary between
        GUI and future Attendance Engine.
        """

        return {
            "configuration_file": Path(
                self.config_entry.get().strip()
            ),
            "output_folder": Path(
                self.output_entry.get().strip()
            ),
            "date_from": self.date_from_entry.get().strip(),
            "date_to": self.date_to_entry.get().strip(),
            "workflow": self.workflow_var.get(),
            "generate_txt": self.generate_txt_var.get(),
            "generate_report": self.generate_report_var.get(),
        }

    def log_process_input(
        self,
        process_input: dict[str, Any],
    ) -> None:
        """Write process input summary to process log."""

        self.append_log(
            f"Configuration file : "
            f"{process_input['configuration_file']}"
        )

        self.append_log(
            f"Output folder      : "
            f"{process_input['output_folder']}"
        )

        self.append_log(
            f"Date From          : "
            f"{process_input['date_from']}"
        )

        self.append_log(
            f"Date To            : "
            f"{process_input['date_to']}"
        )

        self.append_log(
            f"Workflow           : "
            f"{process_input['workflow']}"
        )

        self.append_log(
            f"Generate HRIS TXT  : "
            f"{process_input['generate_txt']}"
        )

        self.append_log(
            f"Generate Report    : "
            f"{process_input['generate_report']}"
        )

    def run_attendance_process(
        self,
        process_input: dict[str, Any],
    ) -> None:
        """Run real Attendance Process Engine."""

        self.generate_button.config(state="disabled")
        self.progress["value"] = 0

        try:
            self.update_status("Reading configuration")
            self.append_log("Reading Attendance Configuration...")
            self.master.update_idletasks()

            configuration_reader = AttendanceConfigurationReader(
                process_input["configuration_file"]
            )

            configuration = configuration_reader.read()

            self.progress["value"] = 15
            self.append_log("Attendance Configuration loaded.")
            self.master.update_idletasks()

            date_from = datetime.strptime(
                process_input["date_from"],
                DATE_FORMAT,
            )

            date_to = datetime.strptime(
                process_input["date_to"],
                DATE_FORMAT,
            )

            self.progress["value"] = 30
            self.update_status("Running Attendance Engine")
            self.append_log("Running Attendance Process Engine...")
            self.master.update_idletasks()

            process_engine = AttendanceProcessEngine()

            result = process_engine.run(
                configuration=configuration,
                output_root=process_input["output_folder"],
                workflow=process_input["workflow"],
                date_from=date_from,
                date_to=date_to,
                generate_txt=process_input["generate_txt"],
                generate_report=process_input["generate_report"],
            )

            self.progress["value"] = 100
            self.update_status("Process finished")

            self._log_process_result(result)

            Dialog.info(
                "Attendance process completed successfully.\n\n"
                f"Job ID: {result['job_id']}\n"
                f"Workflow: {result['workflow']}\n"
                f"Valid Records: {result['valid_record_count']}\n"
                f"Anomaly Records: {result['anomaly_record_count']}"
            )

        except Exception as exc:
            self.progress["value"] = 0
            self.update_status("Process failed")
            self.append_log(f"Process failed: {exc}")

            logger.exception(
                "Attendance process failed."
            )

            Dialog.error(
                "Attendance process failed.\n\n"
                f"{exc}"
            )

        finally:
            self.generate_button.config(state="normal")

    def _log_process_result(
        self,
        result: dict[str, Any],
    ) -> None:
        """Write engine result summary to process log."""

        self.append_log("Attendance process finished.")
        self.append_log(f"Job ID              : {result['job_id']}")
        self.append_log(f"Workflow            : {result['workflow']}")
        self.append_log(f"Raw log count       : {result['raw_log_count']}")
        self.append_log(
            f"Paired record count : {result['paired_record_count']}"
        )
        self.append_log(
            f"Valid record count  : {result['valid_record_count']}"
        )
        self.append_log(
            f"Anomaly count       : {result['anomaly_record_count']}"
        )

        self.append_log("MDB Summary:")

        for item in result["mdb_summary"]:
            self.append_log(
                f"- {item['code']} | "
                f"{item['status']} | "
                f"Raw Logs: {item['raw_log_count']} | "
                f"{item['mdb_path']}"
            )

            if item.get("error"):
                self.append_log(
                    f"  Error: {item['error']}"
                )

        txt_result = result.get("txt_result")

        if txt_result:
            self.append_log(
                f"TXT output folder   : {txt_result['output_folder']}"
            )
            self.append_log(
                f"TXT files generated : {txt_result['total_files']}"
            )

            for file_info in txt_result["generated_files"]:
                self.append_log(
                    f"- TXT: {file_info['file_path']} "
                    f"({file_info['record_count']} rows)"
                )
        else:
            self.append_log("TXT generation skipped.")

        report_result = result.get("report_result")

        if report_result:
            self.append_log(
                f"Report file         : {report_result['report_file']}"
            )
        else:
            self.append_log("Report generation skipped.")

        artifact_result = result.get("artifact_result")

        if artifact_result:
            self.append_log(
                f"Process log         : {artifact_result['process_log']}"
            )
            self.append_log(
                f"Summary JSON        : {artifact_result['summary_json']}"
            )

    # =====================================================
    # VALIDATION
    # =====================================================

    def validate_input(self) -> bool:
        """Validate Attendance GUI input."""

        config_file = self.config_entry.get().strip()
        output_folder = self.output_entry.get().strip()
        date_from_text = self.date_from_entry.get().strip()
        date_to_text = self.date_to_entry.get().strip()
        workflow = self.workflow_var.get()

        result = validate_required(config_file)

        if not result.valid:
            return self._validation_failed(
                "Attendance Configuration is required."
            )

        config_path = Path(config_file)

        result = validate_file(config_path)

        if not result.valid:
            return self._validation_failed(
                f"Attendance Configuration is invalid.\n\n"
                f"{result.message}"
            )

        result = validate_extension(
            config_path,
            (".xlsx",),
        )

        if not result.valid:
            return self._validation_failed(
                "Attendance Configuration must be an Excel file (.xlsx)."
            )

        if self.use_config_output_var.get():
            self.load_output_folder_from_configuration(
                show_warning=False
            )
            output_folder = self.output_entry.get().strip()

        result = validate_required(output_folder)

        if not result.valid:
            return self._validation_failed(
                "Output Folder is required.\n\n"
                "Set OutputFolder in Attendance Configuration or "
                "turn off Same as Configuration File and select it manually."
            )

        output_path = Path(output_folder)

        result = validate_folder(output_path)

        if not result.valid:
            return self._validation_failed(
                f"Output Folder is invalid.\n\n{result.message}"
            )

        result = validate_required(date_from_text)

        if not result.valid:
            return self._validation_failed(
                "Date From is required."
            )

        result = validate_required(date_to_text)

        if not result.valid:
            return self._validation_failed(
                "Date To is required."
            )

        date_from = self._parse_date(date_from_text)

        if date_from is None:
            return self._validation_failed(
                "Date From format is invalid.\n\n"
                "Please use MM/DD/YYYY format.\n"
                "Example: 07/01/2026"
            )

        date_to = self._parse_date(date_to_text)

        if date_to is None:
            return self._validation_failed(
                "Date To format is invalid.\n\n"
                "Please use MM/DD/YYYY format.\n"
                "Example: 07/31/2026"
            )

        if date_from > date_to:
            return self._validation_failed(
                "Date From cannot be greater than Date To."
            )

        if workflow not in ("HO", "Branch"):
            return self._validation_failed(
                "Workflow must be Head Office (HO) or Branch."
            )

        if (
            not self.generate_txt_var.get()
            and not self.generate_report_var.get()
        ):
            return self._validation_failed(
                "Please select at least one output option:\n\n"
                "- Generate HRIS TXT\n"
                "- Generate Excel Report"
            )

        return True

    def _parse_date(self, value: str) -> datetime | None:
        """Parse date using application date format."""

        try:
            return datetime.strptime(
                value,
                DATE_FORMAT,
            )
        except ValueError:
            return None

    def _validation_failed(self, message: str) -> bool:
        """Handle validation failure."""

        self.append_log(f"Validation failed: {message}")
        self.update_status("Validation failed")

        Dialog.warning(message)

        return False

    # =====================================================
    # HELPER
    # =====================================================

    def _configure_ttk_style(self) -> None:
        """Configure themed widget colors."""

        style = ttk.Style(self.master)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Attendance.Horizontal.TProgressbar",
            background=VS_CODE_SUCCESS,
            troughcolor=VS_CODE_SURFACE,
            bordercolor=VS_CODE_BORDER,
            lightcolor=VS_CODE_SUCCESS,
            darkcolor=VS_CODE_SUCCESS_ACTIVE,
        )

    def _apply_widget_theme(self, widget: tk.Misc) -> None:
        """Apply VS Code dark color theme to existing widgets."""

        widget_class = widget.winfo_class()

        if widget_class in {"Toplevel", "Tk"}:
            self._safe_configure(
                widget,
                bg=VS_CODE_BACKGROUND,
            )
        elif widget_class == "Frame":
            parent_class = widget.master.winfo_class()
            frame_bg = (
                VS_CODE_PANEL
                if parent_class == "Labelframe"
                else VS_CODE_BACKGROUND
            )

            self._safe_configure(
                widget,
                bg=frame_bg,
            )
        elif widget_class == "Labelframe":
            self._safe_configure(
                widget,
                bg=VS_CODE_PANEL,
                fg=VS_CODE_MUTED_TEXT,
                highlightbackground=VS_CODE_BORDER,
                highlightcolor=VS_CODE_ACCENT,
            )
        elif widget_class == "Label":
            parent_class = widget.master.winfo_class()
            label_bg = (
                VS_CODE_PANEL
                if parent_class in {"Labelframe", "Frame"}
                else VS_CODE_BACKGROUND
            )

            self._safe_configure(
                widget,
                bg=label_bg,
                fg=VS_CODE_TEXT,
            )
        elif widget_class == "Button":
            self._safe_configure(
                widget,
                bg=VS_CODE_SURFACE,
                fg=VS_CODE_TEXT,
                activebackground=VS_CODE_SURFACE_ACTIVE,
                activeforeground=VS_CODE_TEXT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=VS_CODE_BORDER,
            )
        elif widget_class in {"Radiobutton", "Checkbutton"}:
            self._safe_configure(
                widget,
                bg=VS_CODE_PANEL,
                fg=VS_CODE_TEXT,
                activebackground=VS_CODE_PANEL,
                activeforeground=VS_CODE_MUTED_TEXT,
                selectcolor=VS_CODE_INPUT,
            )
        elif widget_class == "Entry":
            self._safe_configure(
                widget,
                bg=VS_CODE_INPUT,
                fg=VS_CODE_TEXT,
                insertbackground=VS_CODE_TEXT,
                relief="solid",
                bd=1,
                highlightthickness=1,
                highlightbackground=VS_CODE_BORDER,
                highlightcolor=VS_CODE_ACCENT,
            )
        elif widget_class == "Text":
            self._safe_configure(
                widget,
                bg=VS_CODE_INPUT,
                fg=VS_CODE_TEXT,
                insertbackground=VS_CODE_TEXT,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=VS_CODE_BORDER,
            )

        for child in widget.winfo_children():
            self._apply_widget_theme(child)

        if widget is self.status_label:
            self._safe_configure(
                widget,
                bg=VS_CODE_ACCENT,
                fg="#FFFFFF",
            )

    def _style_primary_action(self) -> None:
        """Apply generate action color to the Generate button."""

        self._safe_configure(
            self.generate_button,
            bg=VS_CODE_SUCCESS,
            fg="#FFFFFF",
            activebackground=VS_CODE_SUCCESS_ACTIVE,
            activeforeground="#FFFFFF",
            relief="raised",
            bd=4,
            overrelief="groove",
            highlightthickness=1,
            highlightbackground=VS_CODE_SUCCESS_BORDER,
            highlightcolor=VS_CODE_SUCCESS_BORDER,
        )

    @staticmethod
    def _safe_configure(widget: tk.Misc, **options: Any) -> None:
        """Configure supported widget options only."""

        try:
            widget.configure(**options)
        except tk.TclError:
            pass

    def append_log(self, message: str) -> None:
        """Append message to process log."""

        self.log_text.insert(
            tk.END,
            message + "\n",
        )

        self.log_text.see(tk.END)

        logger.info(message)

    def update_status(self, message: str) -> None:
        """Update status bar."""

        self.status_label.config(
            text=f"Status : {message}"
        )
