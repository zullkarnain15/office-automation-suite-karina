"""
Outlook - Revisi GUI.
"""

from __future__ import annotations

import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from config.app_config import OUTLOOK_ICON
from outlook.engine import OutlookRevisiEngine
from shared.config_manager import OutlookRevisiConfigurationReader
from shared.logger import get_logger

logger = get_logger(__name__)

APP_BACKGROUND = "#EAF2FA"
APP_PANEL = "#F8FBFF"
APP_SURFACE = "#FFFFFF"
APP_INPUT = "#F4F7FB"
APP_BORDER = "#C7D5E6"
APP_TEXT = "#102A43"
APP_MUTED_TEXT = "#60758A"
APP_ACCENT = "#198FA3"
APP_ACCENT_HOVER = "#123B63"
APP_SUCCESS = "#43A58F"
WORKFLOW_ACCENT = "#B45309"
WORKFLOW_ACCENT_HOVER = "#92400E"
APP_LOG_BG = "#24384C"
APP_LOG_FG = "#F4F7FB"
APP_TITLE_FONT = ("Segoe UI", 24, "bold")
APP_SECTION_FONT = ("Segoe UI", 12, "bold")
DEFAULT_FONT = ("Segoe UI", 9)
BUTTON_FONT = ("Segoe UI", 9, "bold")


class OutlookRevisiGUI:
    """Outlook - Revisi module GUI."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.root.title("OAS-K | Outlook - Revisi - by ZSH")
        self.root.geometry("1120x700")
        self.root.minsize(1000, 640)
        self.root.configure(bg=APP_BACKGROUND)

        try:
            self.root.iconbitmap(OUTLOOK_ICON)
        except Exception:
            logger.warning("Outlook icon could not be loaded.")

        self.config_file_var = tk.StringVar(
            value=str(self._ensure_default_configuration())
        )
        self.mailbox_var = tk.StringVar(value="-")
        self.output_root_var = tk.StringVar(value="-")
        self.period_var = tk.StringVar(value="-")
        self.workflow_var = tk.StringVar(value="")
        self.dry_run_var = tk.BooleanVar(value=True)
        self.message_limit_var = tk.StringVar(value="25")
        self.status_var = tk.StringVar(value="Ready.")
        self.total_email_var = tk.StringVar(value="0")
        self.success_email_var = tk.StringVar(value="0")
        self.failed_email_var = tk.StringVar(value="0")
        self.output_txt_var = tk.StringVar(value="0")
        self.report_file_var = tk.StringVar(value="-")
        self.workflow_buttons: dict[str, tk.Button] = {}
        self.workflow_button_labels: dict[str, str] = {}

        self._configure_ttk_style()
        self._create_widgets()
        self._load_configuration_summary()

    def _create_widgets(self) -> None:
        tk.Label(
            self.root,
            text="Outlook - Revisi",
            font=APP_TITLE_FONT,
            bg=APP_BACKGROUND,
            fg=APP_ACCENT_HOVER,
        ).pack(pady=(10, 0))

        tk.Label(
            self.root,
            text="Read Karina mailbox, validate revision emails, and prepare HRIS TXT output",
            font=("Segoe UI", 10),
            bg=APP_BACKGROUND,
            fg=APP_MUTED_TEXT,
        ).pack(pady=(0, 8))

        config_frame = tk.LabelFrame(
            self.root,
            text="Outlook - Revisi Configuration",
            font=APP_SECTION_FONT,
            padx=12,
            pady=10,
            bg=APP_PANEL,
            fg=APP_ACCENT_HOVER,
        )
        config_frame.pack(fill="x", padx=18, pady=(0, 8))
        config_frame.columnconfigure(0, weight=1)

        self.config_entry = tk.Entry(
            config_frame,
            textvariable=self.config_file_var,
            font=DEFAULT_FONT,
            bg=APP_INPUT,
            fg=APP_TEXT,
            relief="solid",
            bd=1,
        )
        self.config_entry.grid(row=0, column=0, sticky="ew", ipady=3)

        tk.Button(
            config_frame,
            text="Browse",
            font=BUTTON_FONT,
            command=self._browse_configuration,
        ).grid(row=0, column=1, padx=(8, 0))

        info_frame = tk.Frame(config_frame, bg=APP_PANEL)
        info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self._add_info(info_frame, 0, "Mailbox", self.mailbox_var)
        self._add_info(info_frame, 1, "Output Root", self.output_root_var)
        self._add_info(info_frame, 2, "Payroll Period", self.period_var)

        control_frame = tk.LabelFrame(
            self.root,
            text="Run Control",
            font=APP_SECTION_FONT,
            padx=12,
            pady=10,
            bg=APP_PANEL,
            fg=APP_ACCENT_HOVER,
        )
        control_frame.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            control_frame,
            text="Processing Workflow",
            font=DEFAULT_FONT,
            bg=APP_PANEL,
            fg=APP_TEXT,
        ).grid(row=0, column=0, sticky="w")

        self._add_workflow_button(
            control_frame,
            label="Head Office",
            value="HO",
            column=1,
            padx=(12, 0),
        )
        self._add_workflow_button(
            control_frame,
            label="Branch",
            value="Branch",
            column=2,
            padx=(8, 24),
        )
        self.workflow_var.trace_add("write", self._refresh_workflow_buttons)
        self._refresh_workflow_buttons()

        tk.Checkbutton(
            control_frame,
            text="Dry Run (no reply, no move email)",
            variable=self.dry_run_var,
            font=DEFAULT_FONT,
            bg=APP_PANEL,
            fg=APP_TEXT,
            activebackground=APP_PANEL,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        tk.Label(
            control_frame,
            text="Email Limit",
            font=DEFAULT_FONT,
            bg=APP_PANEL,
            fg=APP_TEXT,
        ).grid(row=1, column=2, padx=(24, 6), pady=(8, 0), sticky="e")

        tk.Entry(
            control_frame,
            textvariable=self.message_limit_var,
            width=8,
            font=DEFAULT_FONT,
            bg=APP_INPUT,
            relief="solid",
            bd=1,
        ).grid(row=1, column=3, pady=(8, 0), sticky="w")

        self.run_button = tk.Button(
            control_frame,
            text="Run Outlook - Revisi",
            font=BUTTON_FONT,
            bg=APP_SUCCESS,
            fg="white",
            command=self._start_process,
        )
        self.run_button.grid(row=1, column=4, padx=(24, 0), pady=(8, 0))

        result_frame = tk.LabelFrame(
            self.root,
            text="Result",
            font=APP_SECTION_FONT,
            padx=12,
            pady=10,
            bg=APP_PANEL,
            fg=APP_ACCENT_HOVER,
        )
        result_frame.pack(fill="x", padx=18, pady=(0, 8))

        self._add_info(result_frame, 0, "Total Email", self.total_email_var)
        self._add_info(result_frame, 1, "Success", self.success_email_var)
        self._add_info(result_frame, 2, "Failed", self.failed_email_var)
        self._add_info(result_frame, 3, "TXT Output", self.output_txt_var)
        self._add_info(result_frame, 4, "Report File", self.report_file_var)

        self.progress = ttk.Progressbar(
            self.root,
            mode="indeterminate",
            length=500,
        )
        self.progress.pack(fill="x", padx=18, pady=(0, 8))

        log_frame = tk.LabelFrame(
            self.root,
            text="Process Log",
            font=APP_SECTION_FONT,
            padx=8,
            pady=8,
            bg=APP_PANEL,
            fg=APP_ACCENT_HOVER,
        )
        log_frame.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        self.log_text = ScrolledText(
            log_frame,
            height=12,
            font=("Consolas", 9),
            bg=APP_LOG_BG,
            fg=APP_LOG_FG,
            insertbackground=APP_LOG_FG,
            relief="flat",
        )
        self.log_text.pack(fill="both", expand=True)

        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            font=DEFAULT_FONT,
            bg=APP_ACCENT_HOVER,
            fg="white",
            padx=10,
        )
        status_bar.pack(fill="x")

    def _add_workflow_button(
        self,
        parent: tk.Misc,
        *,
        label: str,
        value: str,
        column: int,
        padx: tuple[int, int],
    ) -> None:
        """Add a compact, full-area workflow selector button."""
        button = tk.Button(
            parent,
            text=label,
            font=BUTTON_FONT,
            width=len(label) + 3,
            padx=10,
            pady=2,
            bd=1,
            relief="solid",
            cursor="hand2",
            takefocus=True,
            command=lambda selected=value: self.workflow_var.set(selected),
        )
        button.grid(row=0, column=column, padx=padx, sticky="w")
        self.workflow_buttons[value] = button
        self.workflow_button_labels[value] = label

    def _refresh_workflow_buttons(self, *_args: object) -> None:
        """Show the selected workflow with color and a check mark."""
        selected_workflow = self.workflow_var.get().strip()
        for value, button in self.workflow_buttons.items():
            is_selected = value == selected_workflow
            label = self.workflow_button_labels[value]
            button.configure(
                text=f"\u2713  {label}" if is_selected else label,
                bg=WORKFLOW_ACCENT if is_selected else APP_INPUT,
                fg="white" if is_selected else APP_TEXT,
                activebackground=(
                    WORKFLOW_ACCENT_HOVER if is_selected else APP_BORDER
                ),
                activeforeground="white" if is_selected else APP_TEXT,
                highlightthickness=1,
                highlightbackground=(
                    WORKFLOW_ACCENT if is_selected else APP_BORDER
                ),
                highlightcolor=WORKFLOW_ACCENT_HOVER,
            )

    def _add_info(
        self,
        parent: tk.Misc,
        column: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        container = tk.Frame(parent, bg=APP_PANEL)
        container.grid(row=0, column=column, padx=(0, 18), sticky="w")
        tk.Label(
            container,
            text=label,
            font=("Segoe UI", 8),
            bg=APP_PANEL,
            fg=APP_MUTED_TEXT,
        ).pack(anchor="w")
        tk.Label(
            container,
            textvariable=variable,
            font=DEFAULT_FONT,
            bg=APP_PANEL,
            fg=APP_TEXT,
            wraplength=280,
            justify="left",
        ).pack(anchor="w")

    @staticmethod
    def _ensure_default_configuration() -> Path:
        """Return external config path for source and frozen runs."""
        file_name = "OAS-K_Outlook-Revisi_Configuration.xlsx"
        bundled_path = (
            Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
            / "config"
            / "outlook"
            / file_name
        )
        if not getattr(sys, "frozen", False):
            if bundled_path.exists():
                return bundled_path
            candidates = sorted(
                bundled_path.parent.glob(
                    "OAS-K_Outlook-Revisi_Configuration*.xlsx"
                )
            )
            return candidates[0] if candidates else bundled_path

        external_path = (
            Path(sys.executable).resolve().parent
            / "config"
            / "outlook"
            / file_name
        )
        if not external_path.exists() and bundled_path.exists():
            external_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_path, external_path)
        return external_path

    def _browse_configuration(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Outlook - Revisi Configuration",
            filetypes=[("Excel Workbook", "*.xlsx"), ("All Files", "*.*")],
        )

        if file_path:
            self.config_file_var.set(file_path)
            self._load_configuration_summary()

    def _load_configuration_summary(self) -> None:
        try:
            configuration = OutlookRevisiConfigurationReader(
                self.config_file_var.get()
            ).read()
            self.mailbox_var.set(str(configuration.general.get("Mailbox_SMTP", "-")))
            output_root = configuration.get_output_root()
            self.output_root_var.set(str(output_root) if output_root else "-")
            self.period_var.set(str(configuration.general.get("Payroll_Period", "-")))
            self._append_log("Configuration loaded.")
            self.status_var.set("Configuration ready.")
        except Exception as error:
            self.mailbox_var.set("-")
            self.output_root_var.set("-")
            self.period_var.set("-")
            self._append_log(f"Configuration could not be loaded: {error}")
            self.status_var.set("Configuration not ready.")

    def _start_process(self) -> None:
        workflow = self.workflow_var.get().strip()
        if workflow not in ("HO", "Branch"):
            messagebox.showwarning(
                "Outlook - Revisi",
                "Please select HO or Branch workflow before starting the process.",
                parent=self.root,
            )
            return

        if not Path(self.config_file_var.get()).exists():
            messagebox.showerror(
                "Outlook - Revisi",
                "Configuration file not found.",
                parent=self.root,
            )
            return

        self.run_button.config(state="disabled")
        self.progress.start(10)
        self.status_var.set("Running Outlook - Revisi...")
        self._append_log("Starting Outlook - Revisi process.")

        configuration_file = self.config_file_var.get()
        dry_run = self.dry_run_var.get()
        message_limit = self._message_limit()
        self._append_log(f"Configuration: {configuration_file}")
        self._append_log(f"Selected Workflow: {workflow}")
        self._append_log(f"Mailbox: {self.mailbox_var.get()}")
        self._append_log(f"Dry Run: {dry_run}")

        worker = threading.Thread(
            target=self._run_process_worker,
            args=(configuration_file, workflow, dry_run, message_limit),
            daemon=True,
        )
        worker.start()

    def _run_process_worker(
        self,
        configuration_file: str,
        workflow: str,
        dry_run: bool,
        message_limit: int | None,
    ) -> None:
        com_initialized = False
        try:
            import pythoncom  # type: ignore[import-not-found]

            pythoncom.CoInitialize()
            com_initialized = True
            engine = OutlookRevisiEngine(
                configuration_file=configuration_file,
                workflow=workflow,
                dry_run=dry_run,
                message_limit=message_limit,
            )
            result = engine.run()
            self.root.after(
                0,
                lambda completed_result=result: self._handle_result(
                    completed_result
                ),
            )
        except Exception as error:
            logger.exception("Outlook - Revisi process failed.")
            self.root.after(
                0,
                lambda captured_error=error: self._handle_error(
                    captured_error
                ),
            )
        finally:
            if com_initialized:
                pythoncom.CoUninitialize()

    def _message_limit(self) -> int | None:
        value = self.message_limit_var.get().strip()
        if not value:
            return None
        try:
            limit = int(value)
        except ValueError:
            return 25
        return limit if limit > 0 else None

    def _handle_result(self, result) -> None:
        self.progress.stop()
        self.run_button.config(state="normal")
        self.total_email_var.set(str(result.total_email))
        self.success_email_var.set(str(result.success_email))
        self.failed_email_var.set(str(result.failed_email))
        self.output_txt_var.set(str(result.output_txt_count))
        self.report_file_var.set(str(result.report_file or "-"))
        self.status_var.set(
            "Process finished with warnings."
            if result.final_status == "COMPLETED WITH WARNING"
            else "Process finished."
        )

        self._append_log(f"Job ID: {result.job_id}")
        self._append_log(f"Total Email: {result.total_email}")
        self._append_log(f"Success: {result.success_email}")
        self._append_log(f"Failed: {result.failed_email}")
        self._append_log(f"TXT Output: {result.output_txt_count}")
        self._append_log(f"Report Status: {result.report_status}")
        self._append_log(f"Report File: {result.report_file or '-'}")
        for item in result.message_results:
            if item.status == "SUCCESS":
                continue
            self._append_log(
                f"[{item.status}] {item.sender_email} | {item.subject}"
            )
            for error in item.errors:
                self._append_log(f"- {error}")

        failure_details = []
        for item in result.message_results:
            if item.status != "FAILED":
                continue
            reason = "; ".join(item.errors) or "Unknown validation error."
            failure_details.append(
                f"- {item.sender_email or '(unknown sender)'}: {reason}"
            )
            if len(failure_details) == 3:
                break

        detail_text = ""
        if failure_details:
            detail_text = (
                "\n\nValidation details:\n"
                + "\n".join(failure_details)
                + f"\n\nFull log: {result.process_log}"
            )

        messagebox.showinfo(
            "Outlook - Revisi",
            "Process finished.\n\n"
            f"Success: {result.success_email}\n"
            f"Failed: {result.failed_email}\n"
            f"TXT Output: {result.output_txt_count}"
            f"{detail_text}",
            parent=self.root,
        )

    def _handle_error(self, error: Exception) -> None:
        self.progress.stop()
        self.run_button.config(state="normal")
        self.status_var.set("Process failed.")
        self._append_log(f"Process failed: {error}")
        messagebox.showerror(
            "Outlook - Revisi",
            f"Process failed.\n\n{error}",
            parent=self.root,
        )

    def _append_log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def _configure_ttk_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "TProgressbar",
            troughcolor=APP_SURFACE,
            background=APP_ACCENT,
            bordercolor=APP_BORDER,
            lightcolor=APP_ACCENT,
            darkcolor=APP_ACCENT,
        )


def main() -> None:
    """Run Outlook - Revisi GUI as a standalone module."""
    root = tk.Tk()
    OutlookRevisiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
