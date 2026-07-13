"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : gui.py
Module      : HRIS
Version     : 1.0.0
Python      : 3.14+
=========================================================
HRIS Upload GUI - Sprint 6.23
=========================================================
"""

from __future__ import annotations

import calendar
import os
import shutil
import sys
import threading
import tkinter as tk
from datetime import date
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from config.app_config import DATE_FORMAT
from config.app_config import HRIS_ICON
from config.ui_config import BACKGROUND_COLOR
from config.ui_config import BORDER_COLOR
from config.ui_config import BUTTON_FONT
from config.ui_config import CARD_COLOR
from config.ui_config import DEFAULT_FONT
from config.ui_config import HEADER_FONT
from config.ui_config import PRIMARY_COLOR
from config.ui_config import SECONDARY_COLOR
from config.ui_config import SUCCESS_COLOR
from config.ui_config import TEXT_PRIMARY
from config.ui_config import TEXT_SECONDARY
from hris.engine import HRISFullUploadEngine
from hris.click_profile import HRISClickProfileManager
from shared.config_manager import (
    HRISConfigurationReader,
    resolve_hris_macro_steps,
)
from shared.logger import get_logger

logger = get_logger(__name__)

APP_BACKGROUND = "#EAF2FA"
APP_PANEL = "#F8FBFF"
APP_SURFACE = "#FFFFFF"
APP_SURFACE_ACTIVE = "#E2F2F5"
APP_INPUT = "#F4F7FB"
APP_BORDER = "#C7D5E6"
APP_TEXT = "#102A43"
APP_MUTED_TEXT = "#60758A"
APP_ACCENT = "#198FA3"
APP_ACCENT_HOVER = "#123B63"
APP_SUCCESS = "#43A58F"
APP_SUCCESS_ACTIVE = "#2E8775"
APP_SUCCESS_BORDER = "#247363"
WORKFLOW_ACCENT = "#B45309"
WORKFLOW_ACCENT_HOVER = "#92400E"
APP_LOG_BG = "#24384C"
APP_LOG_FG = "#F4F7FB"
APP_SOFT_ACCENT = "#DDF3F3"
APP_TITLE_FONT = ("Segoe UI", 24, "bold")
APP_SECTION_FONT = ("Segoe UI", 12, "bold")
DEFAULT_FONT = ("Segoe UI", 9)
BUTTON_FONT = ("Segoe UI", 9, "bold")


class HRISUploadGUI:
    """HRIS Upload GUI."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.root.title("OAS-K | HRIS Upload - by ZSH")
        self.root.geometry("1240x720")
        self.root.minsize(1100, 680)
        self.root.configure(bg=APP_BACKGROUND)

        try:
            self.root.iconbitmap(HRIS_ICON)
        except Exception:
            logger.warning("HRIS icon could not be loaded.")

        self.config_file_var = tk.StringVar(
            value=str(self._ensure_default_configuration())
        )
        self.txt_folder_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()
        self.use_config_output_var = tk.BooleanVar(value=True)
        self.workflow_var = tk.StringVar(value="HO")
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.manual_login_var = tk.BooleanVar(value=True)
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.use_date_from_config_var = tk.BooleanVar(value=False)
        self.profile_status_var = tk.StringVar(value="NOT FOUND")

        self.status_var = tk.StringVar(value="Ready.")
        self.job_id_var = tk.StringVar(value="-")
        self.success_count_var = tk.StringVar(value="0")
        self.failed_count_var = tk.StringVar(value="0")
        self.report_folder_var = tk.StringVar(value="-")

        self._configure_ttk_style()
        self._create_widgets()
        self._apply_widget_theme(self.root)
        self._style_primary_action()
        self._refresh_workflow_selector()
        self.toggle_output_source()
        self.toggle_login_mode()
        self._load_assisted_configuration()

    # =====================================================
    # GUI
    # =====================================================

    def _create_widgets(self) -> None:
        self.header_label = tk.Label(
            self.root,
            text="HRIS Upload Module",
            font=APP_TITLE_FONT,
            bg=APP_BACKGROUND,
            fg=APP_ACCENT_HOVER,
        )

        self.header_label.pack(pady=(8, 0))

        self.subtitle_label = tk.Label(
            self.root,
            text="Calibrate, verify, and upload attendance files with confidence",
            font=("Segoe UI", 10),
            bg=APP_BACKGROUND,
            fg=APP_MUTED_TEXT,
        )
        self.subtitle_label.pack(pady=(0, 5))

        frame = tk.LabelFrame(
            self.root,
            text="HRIS Upload Configuration",
            font=APP_SECTION_FONT,
            padx=10,
            pady=6,
        )

        frame.pack(
            fill="x",
            padx=18,
            pady=(0, 8),
        )

        # CONFIGURATION FILE

        tk.Label(
            frame,
            text="HRIS Configuration (.xlsx)",
            font=DEFAULT_FONT,
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 4),
        )

        self.config_entry = tk.Entry(
            frame,
            width=34,
            textvariable=self.config_file_var,
        )

        self.config_entry.grid(
            row=1,
            column=0,
            sticky="we",
            ipady=1,
            pady=(0, 10),
        )

        tk.Button(
            frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self._browse_config_file,
        ).grid(
            row=1,
            column=1,
            sticky="e",
            padx=(8, 18),
            pady=(0, 10),
        )

        # TXT FOLDER

        tk.Label(
            frame,
            text="TXT Folder",
            font=DEFAULT_FONT,
        ).grid(
            row=0,
            column=2,
            columnspan=2,
            sticky="w",
            pady=(0, 4),
        )

        self.txt_folder_entry = tk.Entry(
            frame,
            width=34,
            textvariable=self.txt_folder_var,
        )

        self.txt_folder_entry.grid(
            row=1,
            column=2,
            sticky="we",
            ipady=1,
            pady=(0, 10),
        )

        tk.Button(
            frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self._browse_txt_folder,
        ).grid(
            row=1,
            column=3,
            sticky="e",
            padx=(8, 0),
            pady=(0, 10),
        )

        # OUTPUT FOLDER

        tk.Label(
            frame,
            text="Output Folder",
            font=DEFAULT_FONT,
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 4),
        )

        self.output_entry = tk.Entry(
            frame,
            width=34,
            textvariable=self.output_folder_var,
        )

        self.output_entry.grid(
            row=3,
            column=0,
            sticky="we",
            ipady=1,
            pady=(0, 10),
        )

        self.output_browse_button = tk.Button(
            frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self._browse_output_folder,
        )

        self.output_browse_button.grid(
            row=3,
            column=1,
            sticky="e",
            padx=(8, 18),
            pady=(0, 10),
        )

        tk.Checkbutton(
            frame,
            text="Same as Configuration File",
            variable=self.use_config_output_var,
            font=DEFAULT_FONT,
            command=self.toggle_output_source,
        ).grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 10),
        )

        # DATE RANGE

        tk.Label(
            frame,
            text="Date Range",
            font=DEFAULT_FONT,
        ).grid(
            row=2,
            column=2,
            columnspan=2,
            sticky="w",
            pady=(0, 4),
        )

        date_frame = tk.Frame(frame)

        date_frame.grid(
            row=3,
            column=2,
            columnspan=2,
            sticky="w",
            pady=(0, 2),
        )

        tk.Label(
            date_frame,
            text="From",
            font=DEFAULT_FONT,
        ).pack(side="left")

        self.start_date_entry = tk.Entry(
            date_frame,
            width=12,
            textvariable=self.start_date_var,
        )

        self.start_date_entry.pack(
            side="left",
            padx=(5, 3),
            ipady=1,
        )

        tk.Button(
            date_frame,
            text="Cal",
            width=3,
            command=lambda: self.open_date_picker("start"),
        ).pack(
            side="left",
            padx=(0, 15),
        )

        tk.Label(
            date_frame,
            text="To",
            font=DEFAULT_FONT,
        ).pack(side="left")

        self.end_date_entry = tk.Entry(
            date_frame,
            width=12,
            textvariable=self.end_date_var,
        )

        self.end_date_entry.pack(
            side="left",
            padx=(5, 3),
            ipady=1,
        )

        tk.Button(
            date_frame,
            text="Cal",
            width=3,
            command=lambda: self.open_date_picker("end"),
        ).pack(
            side="left",
            padx=(0, 15),
        )

        tk.Label(
            date_frame,
            text="Format: MM/DD/YYYY",
            font=DEFAULT_FONT,
        ).pack(side="left")

        # LOGIN MODE

        login_frame = tk.LabelFrame(
            frame,
            text="HRIS Login",
            font=APP_SECTION_FONT,
            padx=10,
            pady=6,
        )

        login_frame.grid(
            row=5,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(2, 0),
        )

        tk.Checkbutton(
            login_frame,
            text="Manual login di Microsoft Edge",
            variable=self.manual_login_var,
            font=DEFAULT_FONT,
            command=self.toggle_login_mode,
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 8),
        )

        tk.Label(
            login_frame,
            text="Username",
            font=DEFAULT_FONT,
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 8),
        )

        self.username_entry = tk.Entry(
            login_frame,
            width=36,
            textvariable=self.username_var,
        )

        self.username_entry.grid(
            row=1,
            column=1,
            sticky="we",
            padx=(0, 18),
        )

        tk.Label(
            login_frame,
            text="Password",
            font=DEFAULT_FONT,
        ).grid(
            row=1,
            column=2,
            sticky="w",
            padx=(0, 8),
        )

        self.password_entry = tk.Entry(
            login_frame,
            width=36,
            show="*",
            textvariable=self.password_var,
        )

        self.password_entry.grid(
            row=1,
            column=3,
            sticky="we",
        )

        login_frame.columnconfigure(1, weight=1)
        login_frame.columnconfigure(3, weight=1)

        assisted_frame = tk.Frame(login_frame)
        assisted_frame.grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0)
        )
        tk.Checkbutton(
            assisted_frame,
            text="Use Date From Config",
            variable=self.use_date_from_config_var,
            command=self._toggle_config_dates,
            font=DEFAULT_FONT,
        ).pack(side="left", padx=(0, 12))
        tk.Button(
            assisted_frame,
            text="Calibrate Click Profile",
            command=self._calibrate_click_profile,
            font=BUTTON_FONT,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            assisted_frame,
            text="Open Profile Folder",
            command=self._open_profile_folder,
            font=BUTTON_FONT,
        ).pack(side="left", padx=(0, 8))
        tk.Label(
            assisted_frame,
            textvariable=self.profile_status_var,
            font=DEFAULT_FONT,
        ).pack(side="left")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(2, weight=1)

        # =================================================
        # OPTIONS WRAPPER
        # =================================================

        option_wrapper = tk.Frame(
            self.root,
            bg=APP_BACKGROUND,
        )

        option_wrapper.pack(
            fill="x",
            padx=18,
            pady=(8, 0),
        )

        self._build_workflow_frame(option_wrapper)
        self._build_result_frame(option_wrapper)

        # =================================================
        # ACTION + PROGRESS
        # =================================================

        action_frame = tk.Frame(
            self.root,
            bg=APP_BACKGROUND,
        )

        action_frame.pack(
            fill="x",
            padx=18,
            pady=(8, 0),
        )

        self.start_button = tk.Button(
            action_frame,
            text="Start Upload",
            width=18,
            font=("Segoe UI", 13, "bold"),
            command=self._start_upload,
        )

        self.start_button.pack(
            side="left",
            padx=(0, 12),
            ipady=5,
        )

        tk.Button(
            action_frame,
            text="Reset",
            width=12,
            font=BUTTON_FONT,
            command=self._reset_form,
        ).pack(
            side="left",
            padx=(0, 8),
            ipady=5,
        )

        tk.Button(
            action_frame,
            text="Open Report Folder",
            width=18,
            font=BUTTON_FONT,
            command=self._open_report_folder,
        ).pack(
            side="left",
            padx=(0, 18),
            ipady=5,
        )

        progress_frame = tk.LabelFrame(
            action_frame,
            text="Progress",
            font=APP_SECTION_FONT,
            padx=10,
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
            style="HRIS.Horizontal.TProgressbar",
        )

        self.progress.pack(fill="x")

        # =================================================
        # PROCESS LOG
        # =================================================

        self.log_frame = tk.LabelFrame(
            self.root,
            text="Process Log",
            font=APP_SECTION_FONT,
            padx=10,
            pady=8,
        )

        self.log_frame.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(8, 6),
        )

        self.log_text = ScrolledText(
            self.log_frame,
            height=7,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
        )

        self.log_text.pack(
            fill="both",
            expand=True,
        )

        self._append_log("Application Ready.")
        self._append_log("Waiting for user input...")

        # STATUS BAR

        self.status_label = tk.Label(
            self.root,
            text="Status : Ready",
            anchor="w",
            relief="sunken",
        )

        self.status_label.pack(
            fill="x",
            side="bottom",
        )

    def _build_workflow_frame(self, parent: tk.Frame) -> None:
        workflow_frame = tk.LabelFrame(
            parent,
            text="Workflow",
            font=APP_SECTION_FONT,
            padx=12,
            pady=6,
        )

        workflow_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 8),
        )

        self.workflow_ho_button = tk.Button(
            workflow_frame,
            text="Head Office (HO)",
            width=18,
            font=BUTTON_FONT,
            command=lambda: self._select_workflow("HO"),
            takefocus=True,
        )
        self.workflow_ho_button.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(5, 4),
        )

        self.workflow_branch_button = tk.Button(
            workflow_frame,
            text="Branch",
            width=18,
            font=BUTTON_FONT,
            command=lambda: self._select_workflow("Branch"),
            takefocus=True,
        )
        self.workflow_branch_button.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(4, 5),
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

        workflow_frame.columnconfigure(0, weight=1)
        workflow_frame.columnconfigure(1, weight=1)

    def _build_result_frame(self, parent: tk.Frame) -> None:
        result_frame = tk.LabelFrame(
            parent,
            text="Upload Result",
            font=APP_SECTION_FONT,
            padx=12,
            pady=6,
        )

        result_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(8, 0),
        )

        rows = [
            ("Status", self.status_var, 0, 0),
            ("Job ID", self.job_id_var, 0, 2),
            ("Success", self.success_count_var, 1, 0),
            ("Failed", self.failed_count_var, 1, 2),
            ("Report Folder", self.report_folder_var, 2, 0),
        ]

        for label_text, variable, row_index, column_index in rows:
            tk.Label(
                result_frame,
                text=f"{label_text} :",
                font=DEFAULT_FONT,
            ).grid(
                row=row_index,
                column=column_index,
                sticky="w",
                padx=(5, 12),
                pady=2,
            )

            tk.Label(
                result_frame,
                textvariable=variable,
                font=DEFAULT_FONT,
                wraplength=420,
                justify="left",
            ).grid(
                row=row_index,
                column=column_index + 1,
                columnspan=3 if label_text == "Report Folder" else 1,
                sticky="w",
                pady=2,
            )

        result_frame.columnconfigure(1, weight=1)
        result_frame.columnconfigure(3, weight=1)

    # =====================================================
    # EVENT
    # =====================================================

    @staticmethod
    def _ensure_default_configuration() -> Path:
        """Return a writable external config path for source and frozen runs."""
        file_name = "OAS-K_HRIS_Configuration.xlsx"
        bundled_path = (
            Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            / "config"
            / "hris"
            / file_name
        )
        if not getattr(sys, "frozen", False):
            return bundled_path

        external_path = (
            Path(sys.executable).resolve().parent
            / "config"
            / "hris"
            / file_name
        )
        if not external_path.exists() and bundled_path.exists():
            external_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_path, external_path)
        return external_path

    def _browse_config_file(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select HRIS Configuration File",
            filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
        )
        self._bring_to_front()

        if file_path:
            self.config_file_var.set(file_path)
            self._append_log("HRIS Configuration selected.")
            self.update_status("Configuration selected")

            if self.use_config_output_var.get():
                self.load_output_folder_from_configuration(
                    show_warning=True
                )
            self._load_assisted_configuration()

    def _load_assisted_configuration(self) -> None:
        config_file = self.config_file_var.get().strip()
        if not config_file:
            return
        try:
            configuration = HRISConfigurationReader(config_file).read()
            self.use_date_from_config_var.set(
                str(configuration.upload.get("Use_Date_From_Config", False))
                .strip().lower() in {"true", "1", "yes", "y"}
            )
            if self.use_date_from_config_var.get():
                self.start_date_var.set(
                    str(configuration.upload.get("Start_Date", "") or "")
                )
                self.end_date_var.set(
                    str(configuration.upload.get("End_Date", "") or "")
                )
            profile_path = HRISClickProfileManager.resolve_profile_path(
                configuration
            )
            self.profile_status_var.set(
                self._get_profile_status(configuration, profile_path)
            )
            self._toggle_config_dates()
        except Exception as error:
            self.profile_status_var.set("Click Profile Status: NOT FOUND")
            self._append_log(f"Assisted configuration could not be loaded: {error}")

    def _toggle_config_dates(self) -> None:
        if self.use_date_from_config_var.get():
            config_file = self.config_file_var.get().strip()
            if config_file:
                try:
                    configuration = HRISConfigurationReader(config_file).read()
                    self.start_date_var.set(
                        str(configuration.upload.get("Start_Date", "") or "")
                    )
                    self.end_date_var.set(
                        str(configuration.upload.get("End_Date", "") or "")
                    )
                except Exception as error:
                    self._append_log(
                        f"Configured dates could not be loaded: {error}"
                    )
        state = "disabled" if self.use_date_from_config_var.get() else "normal"
        self.start_date_entry.config(state=state)
        self.end_date_entry.config(state=state)

    def _calibrate_click_profile(self) -> None:
        config_file = self.config_file_var.get().strip()
        if not config_file:
            self._validation_failed("Select HRIS Configuration first.")
            return

        def worker() -> None:
            try:
                from hris.assisted_calibrator import HRISAssistedCalibrator
                calibrator = HRISAssistedCalibrator(
                    config_file,
                    instruction_callback=self._wait_for_calibration_navigation,
                    coordinate_callback=self._capture_calibration_point,
                )
                path = calibrator.run()
                self.root.after(
                    0,
                    lambda: self.profile_status_var.set(
                        "Click Profile Status: READY"
                    ),
                )
                self.root.after(
                    0, lambda: self._append_log(f"Click profile saved: {path}")
                )
            except Exception as error:
                self.root.after(
                    0, lambda calibration_error=error: self._handle_upload_error(
                        calibration_error
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    def _wait_for_calibration_navigation(self, message: str) -> None:
        confirmed = threading.Event()
        cancelled = {"value": False}

        def prompt() -> None:
            if not messagebox.askokcancel(
                "HRIS Calibration - Manual Navigation",
                f"{message}\n\nKlik OK hanya setelah halaman upload siap.",
                parent=self.root,
            ):
                cancelled["value"] = True
            confirmed.set()

        self.root.after(0, prompt)
        confirmed.wait()
        if cancelled["value"]:
            raise RuntimeError("Click profile calibration cancelled.")

    def _capture_calibration_point(self, message: str) -> tuple[int, int]:
        """Capture the pointer with global F8 while Edge remains interactive."""
        from hris.global_hotkey import WindowsGlobalHotkey

        completed = threading.Event()
        dialog_ready = threading.Event()
        result: dict[str, Any] = {"cancelled": False}
        dialog_holder: dict[str, tk.Toplevel] = {}

        def finish_capture() -> None:
            dialog = dialog_holder.get("dialog")
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()
            try:
                self.root.bell()
            except tk.TclError:
                pass
            completed.set()

        def close_dialog() -> None:
            dialog = dialog_holder.get("dialog")
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()

        def capture_hotkey() -> None:
            if completed.is_set():
                return
            import pyautogui

            position = pyautogui.position()
            result["coordinate"] = (int(position.x), int(position.y))
            self.root.after(0, finish_capture)

        def prompt() -> None:
            dialog = tk.Toplevel(self.root)
            dialog_holder["dialog"] = dialog
            dialog.title("HRIS Click Calibration")
            dialog.geometry(
                f"460x250+{max(10, dialog.winfo_screenwidth() - 480)}+40"
            )
            dialog.resizable(False, False)
            dialog.attributes("-topmost", True)

            tk.Label(
                dialog,
                text=message,
                justify="left",
                wraplength=420,
                padx=18,
                pady=18,
            ).pack(fill="both", expand=True)
            tk.Label(
                dialog,
                text=(
                    "Arahkan pointer ke target di Edge,\n"
                    "lalu tekan F8 untuk REKAM."
                ),
                font=("Segoe UI", 12, "bold"),
                fg=APP_ACCENT_HOVER,
                pady=8,
            ).pack()
            tk.Button(
                dialog,
                text="Cancel Calibration",
                command=lambda: cancel(),
                font=BUTTON_FONT,
            ).pack(pady=(0, 14))

            def cancel(_event: object | None = None) -> None:
                if completed.is_set():
                    return
                result["cancelled"] = True
                dialog.destroy()
                completed.set()

            dialog.bind("<Escape>", cancel)
            dialog.protocol("WM_DELETE_WINDOW", cancel)
            dialog_ready.set()

        self.root.after(0, prompt)
        dialog_ready.wait()
        listener = WindowsGlobalHotkey(capture_hotkey)
        try:
            listener.start()
            completed.wait()
        finally:
            listener.stop()
            if not completed.is_set():
                self.root.after(0, close_dialog)
        if result["cancelled"]:
            raise RuntimeError("Click profile calibration cancelled.")
        return result["coordinate"]

    def _get_profile_status(
        self,
        configuration: object,
        profile_path: Path,
    ) -> str:
        if not profile_path.exists():
            return "Click Profile Status: NOT FOUND"
        try:
            import pyautogui

            profile = HRISClickProfileManager.load_profile(profile_path)
            screen = pyautogui.size()
            validation = HRISClickProfileManager.validate_profile(
                profile,
                (int(screen.width), int(screen.height)),
                configuration.upload,
                current_scale_percent=self._get_display_scale_percent(),
                required_steps=resolve_hris_macro_steps(
                    configuration.assisted_steps
                ),
            )
            return f"Click Profile Status: {validation.message}"
        except Exception as error:
            logger.warning("Click profile validation failed: %s", error)
            return "Click Profile Status: NOT FOUND"

    @staticmethod
    def _get_display_scale_percent() -> int:
        try:
            import ctypes
            return round(ctypes.windll.shcore.GetScaleFactorForDevice(0))
        except Exception:
            return 100

    def _open_profile_folder(self) -> None:
        try:
            configuration = HRISConfigurationReader(
                self.config_file_var.get().strip()
            ).read()
            folder = HRISClickProfileManager.resolve_profile_path(
                configuration
            ).parent
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
        except Exception as error:
            self._validation_failed(str(error))

    def _browse_txt_folder(self) -> None:
        folder_path = filedialog.askdirectory(
            parent=self.root,
            title="Select TXT Folder",
        )
        self._bring_to_front()

        if folder_path:
            self.txt_folder_var.set(folder_path)
            self._append_log("TXT folder selected.")
            self.update_status("TXT folder selected")

    def _browse_output_folder(self) -> None:
        folder_path = filedialog.askdirectory(
            parent=self.root,
            title="Select Output Folder",
        )
        self._bring_to_front()

        if folder_path:
            self.output_folder_var.set(folder_path)
            self._append_log("Output folder selected.")
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
                self._append_log(
                    "Output folder source: HRIS Configuration."
                )
        else:
            self.output_entry.config(state="normal")
            self.output_browse_button.config(state="normal")

            if hasattr(self, "log_text"):
                self._append_log("Output folder source: Manual selection.")

    def load_output_folder_from_configuration(
        self,
        show_warning: bool,
    ) -> bool:
        """Load output folder from selected HRIS Configuration."""

        config_file = self.config_file_var.get().strip()

        if not config_file:
            return False

        try:
            configuration_reader = HRISConfigurationReader(config_file)
            configuration = configuration_reader.read()
            output_folder = configuration.get_output_folder()
        except Exception as exc:
            if hasattr(self, "log_text"):
                self._append_log(
                    f"Failed to read output folder from configuration: {exc}"
                )

            if show_warning:
                messagebox.showwarning(
                    "HRIS Configuration",
                    "Output Folder could not be read from "
                    "HRIS Configuration.\n\n"
                    f"{exc}",
                    parent=self.root,
                )
                self._bring_to_front()

            return False

        if output_folder is None:
            if hasattr(self, "log_text"):
                self._append_log(
                    "Folder_Upload_Path is not set in HRIS Configuration."
                )

            if show_warning:
                messagebox.showwarning(
                    "HRIS Configuration",
                    "Folder_Upload_Path is not set in "
                    "HRIS Configuration.",
                    parent=self.root,
                )
                self._bring_to_front()

            return False

        self.output_entry.config(state="normal")
        self.output_folder_var.set(str(output_folder))

        if self.use_config_output_var.get():
            self.output_entry.config(state="disabled")

        if hasattr(self, "log_text"):
            self._append_log(
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

        self._refresh_workflow_selector()
        self.workflow_status_label.config(text=text)
        self._append_log(text)

    def _select_workflow(self, workflow: str) -> None:
        """Select a workflow through the compact card controls."""

        if workflow not in ("HO", "Branch"):
            return

        self.workflow_var.set(workflow)
        self.update_workflow_status()

    def _refresh_workflow_selector(self) -> None:
        """Refresh the selected and unselected workflow card colors."""

        selected_workflow = self.workflow_var.get()
        buttons = (
            ("HO", "Head Office (HO)", self.workflow_ho_button),
            ("Branch", "Branch", self.workflow_branch_button),
        )

        for workflow, label, button in buttons:
            is_selected = workflow == selected_workflow
            self._safe_configure(
                button,
                text=f"\u2713  {label}" if is_selected else label,
                bg=WORKFLOW_ACCENT if is_selected else APP_INPUT,
                fg="#FFFFFF" if is_selected else APP_TEXT,
                activebackground=(
                    WORKFLOW_ACCENT_HOVER if is_selected else APP_SOFT_ACCENT
                ),
                activeforeground="#FFFFFF" if is_selected else APP_TEXT,
                relief="solid",
                bd=1,
                highlightthickness=1,
                highlightbackground=(
                    WORKFLOW_ACCENT if is_selected else APP_BORDER
                ),
                highlightcolor=WORKFLOW_ACCENT,
                cursor="hand2",
            )

    def toggle_login_mode(self) -> None:
        """Toggle HRIS credential fields based on login mode."""

        if self.manual_login_var.get():
            self.username_entry.config(state="disabled")
            self.password_entry.config(state="disabled")

            if hasattr(self, "log_text"):
                self._append_log("Login mode: Manual login in Microsoft Edge.")
        else:
            self.username_entry.config(state="normal")
            self.password_entry.config(state="normal")

            if hasattr(self, "log_text"):
                self._append_log("Login mode: Automatic login from GUI.")

    def _start_upload(self) -> None:
        self._append_log("Start Upload button clicked.")
        self.update_status("Validating input")

        if not self._validate_inputs():
            return

        self.start_button.config(state="disabled")
        self.progress["value"] = 15
        self._clear_log()
        self._append_log("Input validation success.")
        self._append_log("Starting HRIS upload...")
        self.update_status("Running HRIS upload")

        thread = threading.Thread(target=self._run_upload_worker, daemon=True)
        thread.start()

    # =====================================================
    # DATE PICKER
    # =====================================================

    def open_date_picker(self, target: str) -> None:
        """Open simple calendar date picker."""

        initial_date = self._get_initial_picker_date(target)

        picker = tk.Toplevel(self.root)
        picker.title("Select Date")
        picker.geometry("320x300")
        picker.resizable(False, False)
        picker.transient(self.root)
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

            if target == "start":
                self.start_date_var.set(formatted_date)
                self._append_log(f"Date From selected: {formatted_date}")
            else:
                self.end_date_var.set(formatted_date)
                self._append_log(f"Date To selected: {formatted_date}")

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

        if target == "start":
            value = self.start_date_var.get().strip()
        else:
            value = self.end_date_var.get().strip()

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

    def _run_upload_worker(self) -> None:
        """Run HRIS upload engine."""

        try:
            configuration_file = Path(
                self.config_file_var.get().strip()
            )

            engine = HRISFullUploadEngine(
                configuration_file=configuration_file,
                txt_folder=self.txt_folder_var.get(),
                output_root=self.output_folder_var.get(),
                workflow=self.workflow_var.get(),
                start_date=self.start_date_var.get(),
                end_date=self.end_date_var.get(),
                wait_for_manual_login=self.manual_login_var.get(),
                manual_login_callback=self._wait_for_manual_login_confirmation,
                manual_checkpoint_callback=self._wait_for_manual_checkpoint,
                hris_username=self.username_var.get().strip(),
                hris_password=self.password_var.get(),
                close_browser_on_error=False,
                manual_verification_callback=(
                    self._wait_for_assisted_verification
                ),
            )

            result = engine.run()

            self.root.after(
                0,
                lambda: self._handle_upload_result(result),
            )

        except Exception as error:
            logger.exception("HRIS upload failed from GUI.")
            self.root.after(
                0,
                lambda upload_error=error: self._handle_upload_error(
                    upload_error
                ),
            )

    def _wait_for_manual_login_confirmation(self) -> None:
        """Wait for operator confirmation after manual HRIS login."""

        login_confirmed = threading.Event()
        login_cancelled = {"value": False}

        def show_login_prompt() -> None:
            self._append_log(
                "HRIS browser opened. Waiting for manual login confirmation."
            )
            confirmed = messagebox.askokcancel(
                "HRIS Manual Login",
                "Silakan login username dan password di browser HRIS "
                "yang sudah terbuka.\n\n"
                "Setelah login berhasil dan halaman HRIS siap, "
                "kembali ke aplikasi ini lalu klik OK untuk lanjut upload.\n\n"
                "Klik Cancel untuk membatalkan upload.",
                parent=self.root,
            )
            self._bring_to_front()

            if not confirmed:
                self._append_log("Manual HRIS login cancelled.")
                login_cancelled["value"] = True
                login_confirmed.set()
                return

            self._append_log("Manual HRIS login confirmed.")
            login_confirmed.set()

        self.root.after(0, show_login_prompt)
        login_confirmed.wait()

        if login_cancelled["value"]:
            raise RuntimeError("Manual HRIS login cancelled by user.")

    def _wait_for_manual_checkpoint(self, message: str) -> None:
        """Wait for operator confirmation for a manual HRIS checkpoint."""

        checkpoint_confirmed = threading.Event()
        checkpoint_cancelled = {"value": False}

        def show_checkpoint_prompt() -> None:
            self._append_log("Automation paused for manual HRIS checkpoint.")
            confirmed = messagebox.askokcancel(
                "HRIS Manual Checkpoint",
                (
                    f"{message}\n\n"
                    "Silakan lakukan penyesuaian di browser HRIS yang terbuka. "
                    "Setelah halaman/elemen sudah siap, kembali ke aplikasi ini "
                    "lalu klik OK untuk mencoba lanjut otomatis.\n\n"
                    "Klik Cancel untuk membatalkan upload."
                ),
                parent=self.root,
            )
            self._bring_to_front()

            if not confirmed:
                self._append_log("Manual HRIS checkpoint cancelled.")
                checkpoint_cancelled["value"] = True
                checkpoint_confirmed.set()
                return

            self._append_log("Manual HRIS checkpoint confirmed.")
            checkpoint_confirmed.set()

        self.root.after(0, show_checkpoint_prompt)
        checkpoint_confirmed.wait()

        if checkpoint_cancelled["value"]:
            raise RuntimeError("Manual HRIS checkpoint cancelled by user.")

    def _wait_for_assisted_verification(self, message: str) -> str:
        """Let the operator resolve an ambiguous HRIS submission result."""
        completed = threading.Event()
        result = {"action": "stop"}

        def show_verification_panel() -> None:
            panel = tk.Toplevel(self.root)
            panel.title("HRIS Submission Verification")
            panel.geometry(
                f"540x360+{max(10, panel.winfo_screenwidth() - 560)}+60"
            )
            panel.resizable(False, False)
            panel.attributes("-topmost", True)

            tk.Label(
                panel,
                text="Verification result is unclear",
                font=APP_SECTION_FONT,
                fg=APP_ACCENT_HOVER,
                pady=14,
            ).pack()
            tk.Label(
                panel,
                text=message,
                justify="left",
                wraplength=500,
                padx=18,
                pady=8,
            ).pack(fill="both", expand=True)

            button_frame = tk.Frame(panel)
            button_frame.pack(fill="x", padx=14, pady=14)

            def choose(action: str) -> None:
                result["action"] = action
                panel.destroy()
                completed.set()

            for label, action in (
                ("Confirm Submitted", "submitted"),
                ("Mark Failed", "failed"),
                ("Retry Verification", "retry"),
                ("Stop Batch", "stop"),
            ):
                tk.Button(
                    button_frame,
                    text=label,
                    command=lambda value=action: choose(value),
                    font=BUTTON_FONT,
                ).pack(side="left", padx=4)

            panel.protocol("WM_DELETE_WINDOW", lambda: choose("stop"))

        self.root.after(0, show_verification_panel)
        completed.wait()
        return result["action"]

    def _handle_upload_result(self, result: object) -> None:
        self.start_button.config(state="normal")
        self.status_var.set("SUCCESS" if result.success else "FAILED")
        self.progress["value"] = 100 if result.success else 0
        self.job_id_var.set(result.job_id or "-")
        self.success_count_var.set(str(result.success_count))
        self.failed_count_var.set(str(result.failed_count))
        self.report_folder_var.set(str(result.report_folder or "-"))
        self._append_log(result.message)

        if getattr(result, "diagnostic_folder", None):
            self._append_log(
                f"Diagnostic folder: {result.diagnostic_folder}"
            )

        if getattr(result, "diagnostic_zip_file", None):
            self._append_log(
                f"Diagnostic ZIP: {result.diagnostic_zip_file}"
            )

        if result.success:
            self.update_status("Upload completed")
            messagebox.showinfo(
                "HRIS Upload",
                "HRIS upload completed successfully.",
                parent=self.root,
            )
            self._bring_to_front()
        else:
            self.progress["value"] = 0
            self.update_status("Upload failed")
            messagebox.showerror(
                "HRIS Upload",
                result.message,
                parent=self.root,
            )
            self._bring_to_front()

    def _handle_upload_error(self, error: Exception) -> None:
        self.start_button.config(state="normal")
        self.progress["value"] = 0
        self.status_var.set("FAILED")
        self._append_log(str(error))
        self.update_status("Upload failed")
        messagebox.showerror(
            "HRIS Upload Error",
            str(error),
            parent=self.root,
        )
        self._bring_to_front()

    # =====================================================
    # VALIDATION
    # =====================================================

    def _validate_inputs(self) -> bool:
        config_file = Path(self.config_file_var.get().strip())
        txt_folder = Path(self.txt_folder_var.get().strip())
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not config_file.exists():
            return self._validation_failed(
                "HRIS Configuration file is required."
            )

        if config_file.suffix.lower() != ".xlsx":
            return self._validation_failed(
                "HRIS Configuration file must be .xlsx."
            )

        if not txt_folder.exists() or not txt_folder.is_dir():
            return self._validation_failed("TXT Folder is required.")

        if self.use_config_output_var.get():
            self.load_output_folder_from_configuration(
                show_warning=False
            )

        output_folder = Path(self.output_folder_var.get().strip())

        if not output_folder.exists() or not output_folder.is_dir():
            return self._validation_failed(
                "Output Folder is required.\n\n"
                "Set Folder_Upload_Path in HRIS Configuration or "
                "turn off Same as Configuration File and select it manually."
            )

        if not start_date or not end_date:
            return self._validation_failed(
                "Start Date and End Date are required."
            )

        parsed_start_date = self._parse_date(start_date)
        parsed_end_date = self._parse_date(end_date)

        if parsed_start_date is None:
            return self._validation_failed(
                "Start Date format is invalid.\n\n"
                "Please use MM/DD/YYYY format.\n"
                "Example: 07/01/2026"
            )

        if parsed_end_date is None:
            return self._validation_failed(
                "End Date format is invalid.\n\n"
                "Please use MM/DD/YYYY format.\n"
                "Example: 07/31/2026"
            )

        if parsed_start_date > parsed_end_date:
            return self._validation_failed(
                "Start Date cannot be greater than End Date."
            )

        if self.workflow_var.get() not in ("HO", "Branch"):
            return self._validation_failed(
                "Workflow must be Head Office (HO) or Branch."
            )

        if not self.manual_login_var.get():
            if not self.username_var.get().strip():
                return self._validation_failed(
                    "Username is required for automatic HRIS login."
                )

            if not self.password_var.get():
                return self._validation_failed(
                    "Password is required for automatic HRIS login."
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

        self._append_log(f"Validation failed: {message}")
        self.update_status("Validation failed")
        messagebox.showwarning(
            "Validation Error",
            message,
            parent=self.root,
        )
        self._bring_to_front()

        return False

    # =====================================================
    # HELPER
    # =====================================================

    def _reset_form(self) -> None:
        self.config_file_var.set("")
        self.txt_folder_var.set("")
        self.output_folder_var.set("")
        self.workflow_var.set("HO")
        self.use_config_output_var.set(True)
        self.manual_login_var.set(True)
        self.username_var.set("")
        self.password_var.set("")
        self.use_date_from_config_var.set(False)
        self.profile_status_var.set("Click Profile Status: NOT FOUND")
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.status_var.set("Ready.")
        self.job_id_var.set("-")
        self.success_count_var.set("0")
        self.failed_count_var.set("0")
        self.report_folder_var.set("-")
        self.progress["value"] = 0
        self._clear_log()
        self._append_log("Application Ready.")
        self._append_log("Waiting for user input...")
        self.workflow_status_label.config(
            text="Selected Workflow : Head Office (HO)"
        )
        self._refresh_workflow_selector()
        self.toggle_output_source()
        self.toggle_login_mode()
        self.update_status("Ready")

    def _open_report_folder(self) -> None:
        report_folder = self.report_folder_var.get().strip()

        if not report_folder or report_folder == "-":
            messagebox.showinfo(
                "Report Folder",
                "No report folder available yet.",
                parent=self.root,
            )
            self._bring_to_front()
            return

        folder_path = Path(report_folder)

        if not folder_path.exists():
            messagebox.showerror(
                "Report Folder",
                "Report folder does not exist.",
                parent=self.root,
            )
            self._bring_to_front()
            return

        os.startfile(folder_path)

    def _configure_ttk_style(self) -> None:
        """Configure themed widget colors."""

        style = ttk.Style(self.root)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "HRIS.Horizontal.TProgressbar",
            background=APP_SUCCESS,
            troughcolor="#E2E9F2",
            bordercolor=APP_BORDER,
            lightcolor=APP_SUCCESS,
            darkcolor=APP_SUCCESS_ACTIVE,
            thickness=22,
        )

    def _apply_widget_theme(self, widget: tk.Misc) -> None:
        """Apply launcher color theme to existing widgets."""

        widget_class = widget.winfo_class()

        if widget_class in {"Toplevel", "Tk"}:
            self._safe_configure(
                widget,
                bg=APP_BACKGROUND,
            )
        elif widget_class == "Frame":
            parent_class = widget.master.winfo_class()
            frame_bg = (
                APP_PANEL
                if parent_class == "Labelframe"
                else APP_BACKGROUND
            )

            self._safe_configure(
                widget,
                bg=frame_bg,
            )
        elif widget is getattr(self, "log_frame", None):
            self._safe_configure(
                widget,
                bg=APP_LOG_BG,
                fg=APP_LOG_FG,
                highlightbackground=APP_LOG_BG,
                highlightcolor=APP_LOG_BG,
            )
        elif widget_class == "Labelframe":
            self._safe_configure(
                widget,
                bg=APP_PANEL,
                fg=APP_ACCENT_HOVER,
                relief="solid",
                bd=1,
                highlightthickness=1,
                highlightbackground=APP_BORDER,
                highlightcolor=APP_ACCENT,
            )
        elif widget_class == "Label":
            parent_class = widget.master.winfo_class()
            parent_bg = None

            try:
                parent_bg = widget.master.cget("bg")
            except tk.TclError:
                parent_bg = None

            if parent_class in {"Labelframe", "Frame"} and parent_bg:
                label_bg = parent_bg
            else:
                label_bg = APP_BACKGROUND

            self._safe_configure(
                widget,
                bg=label_bg,
                fg=APP_TEXT,
            )
        elif widget_class == "Button":
            self._safe_configure(
                widget,
                bg=APP_ACCENT,
                fg="#FFFFFF",
                activebackground=APP_ACCENT_HOVER,
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=APP_BORDER,
            )
        elif widget_class in {"Radiobutton", "Checkbutton"}:
            parent_bg = APP_PANEL

            try:
                parent_bg = widget.master.cget("bg")
            except tk.TclError:
                pass

            self._safe_configure(
                widget,
                bg=parent_bg,
                fg=APP_TEXT,
                activebackground=parent_bg,
                activeforeground=APP_MUTED_TEXT,
                selectcolor=APP_SOFT_ACCENT,
            )
        elif widget_class == "Entry":
            self._safe_configure(
                widget,
                bg=APP_INPUT,
                fg=APP_TEXT,
                insertbackground=APP_TEXT,
                relief="solid",
                bd=1,
                highlightthickness=1,
                highlightbackground=APP_BORDER,
                highlightcolor=APP_ACCENT,
                disabledbackground="#E8EEF5",
                disabledforeground=APP_MUTED_TEXT,
            )
        elif widget_class == "Text":
            text_bg = APP_INPUT
            text_fg = APP_TEXT
            border_color = APP_BORDER

            if widget.master is getattr(self, "log_frame", None):
                text_bg = APP_LOG_BG
                text_fg = APP_LOG_FG
                border_color = APP_LOG_BG

            self._safe_configure(
                widget,
                bg=text_bg,
                fg=text_fg,
                insertbackground=text_fg,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=border_color,
            )

        for child in widget.winfo_children():
            self._apply_widget_theme(child)

        if widget is getattr(self, "status_label", None):
            self._safe_configure(
                widget,
                bg=APP_ACCENT_HOVER,
                fg="#FFFFFF",
                relief="flat",
                padx=12,
                pady=4,
                font=("Segoe UI", 9, "bold"),
            )
        elif widget is getattr(self, "header_label", None):
            self._safe_configure(
                widget,
                bg=APP_BACKGROUND,
                fg=APP_ACCENT_HOVER,
            )
        elif widget is getattr(self, "subtitle_label", None):
            self._safe_configure(
                widget,
                bg=APP_BACKGROUND,
                fg=APP_MUTED_TEXT,
            )

    def _style_primary_action(self) -> None:
        """Apply upload action color to the Start Upload button."""

        self._safe_configure(
            self.start_button,
            bg=APP_SUCCESS,
            fg="#FFFFFF",
            activebackground=APP_SUCCESS_ACTIVE,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            overrelief="flat",
            highlightthickness=1,
            highlightbackground=APP_SUCCESS_BORDER,
            highlightcolor=APP_SUCCESS_BORDER,
            cursor="hand2",
        )

    @staticmethod
    def _safe_configure(widget: tk.Misc, **options: Any) -> None:
        """Configure supported widget options only."""

        try:
            widget.configure(**options)
        except tk.TclError:
            pass

    def _bring_to_front(self) -> None:
        """Bring HRIS window back after native dialogs."""

        try:
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _append_log(self, message: str) -> None:
        """Append message to process log."""

        self.log_text.config(state="normal")
        self.log_text.insert(
            tk.END,
            message + "\n",
        )
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

        logger.info(message)

    def _clear_log(self) -> None:
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def update_status(self, message: str) -> None:
        """Update status bar."""

        self.status_label.config(
            text=f"Status : {message}"
        )


def main() -> None:
    root = tk.Tk()
    HRISUploadGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
