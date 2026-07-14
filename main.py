"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : main.py
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
Application Entry Point
=========================================================
"""

from __future__ import annotations

from functools import partial
import tkinter as tk
from tkinter import messagebox

from attendance.gui import AttendanceGUI
from config.app_config import (
    APP_ICON,
    APP_VERSION,
    IMAGE_PATH,
    WINDOW_TITLE,
)
from config.ui_config import (
    BACKGROUND_COLOR,
    BORDER_COLOR,
    BUTTON_FONT,
    CARD_COLOR,
    DEFAULT_FONT,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    SUCCESS_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WINDOW_HEIGHT,
    WINDOW_RESIZABLE,
    WINDOW_WIDTH,
)
from hris.gui import HRISUploadGUI
from outlook.gui import OutlookRevisiGUI
from shared.logger import get_logger

logger = get_logger(__name__)

APP_BACKGROUND = BACKGROUND_COLOR
APP_PANEL = CARD_COLOR
APP_TEXT = TEXT_PRIMARY
APP_MUTED_TEXT = TEXT_SECONDARY
APP_ACCENT = SECONDARY_COLOR
APP_ACCENT_HOVER = PRIMARY_COLOR
APP_SUCCESS = SUCCESS_COLOR
APP_SUCCESS_ACTIVE = "#257A4C"
APP_BORDER = BORDER_COLOR
APP_TITLE_FONT = ("Segoe UI", 22, "bold")
APP_SECTION_FONT = ("Segoe UI", 13, "bold")
APP_CARD_TITLE_FONT = ("Segoe UI", 12, "bold")


# =========================================================
# EVENT
# =========================================================

def coming_soon(module_name: str) -> None:
    """Temporary event for unavailable modules."""

    logger.info("%s module clicked.", module_name)

    messagebox.showinfo(
        "Coming Soon",
        f"{module_name} module is under development.",
    )

def open_hris_module(root: tk.Tk) -> None:
    """Open HRIS Upload module."""

    logger.info("HRIS module opened.")

    hris_window = tk.Toplevel(root)
    hris_window.transient(root)
    HRISUploadGUI(hris_window)
    hris_window.lift()
    hris_window.focus_force()


def open_attendance_module(root: tk.Tk) -> None:
    """Open Attendance module."""

    logger.info("Attendance module opened.")

    attendance_window = tk.Toplevel(root)
    attendance_window.transient(root)
    AttendanceGUI(attendance_window)
    attendance_window.lift()
    attendance_window.focus_force()


def open_outlook_module(root: tk.Tk) -> None:
    """Open Outlook - Revisi module."""

    logger.info("Outlook - Revisi module opened.")

    outlook_window = tk.Toplevel(root)
    outlook_window.transient(root)
    OutlookRevisiGUI(outlook_window)
    outlook_window.lift()
    outlook_window.focus_force()


def open_utilities_module(root: tk.Tk) -> None:
    """Open Comparison-Attendance Reconciliation through a lazy import."""
    try:
        from utilities.attendance_reconciliation.gui import (
            AttendanceReconciliationGUI,
        )

        logger.info("Comparison-Attendance Reconciliation module opened.")
        utilities_window = tk.Toplevel(root)
        utilities_window.transient(root)
        AttendanceReconciliationGUI(utilities_window)
        utilities_window.lift()
        utilities_window.focus_force()
    except Exception as error:
        logger.exception("Utilities reconciliation module could not be opened.")
        messagebox.showerror(
            "Office Automation Suite - Karina",
            "Gagal membuka Comparison-Attendance Reconciliation.\n\n"
            f"{error}",
            parent=root,
        )


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    logger.info("Starting OAS-K")

    root = tk.Tk()

    root.title(WINDOW_TITLE)

    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

    root.configure(bg=APP_BACKGROUND)

    root.resizable(
        WINDOW_RESIZABLE,
        WINDOW_RESIZABLE,
    )

    try:
        root.iconbitmap(APP_ICON)
    except Exception:
        logger.warning("Application icon could not be loaded.")

    status_var = tk.StringVar(value="Status : Ready")

    def launch_module(
        module_name: str,
        command: object,
    ) -> None:
        status_var.set(f"Status : Opening {module_name}")
        command()

    # =====================================================
    # Header
    # =====================================================

    shell = tk.Frame(
        root,
        bg=APP_BACKGROUND,
    )

    shell.pack(
        fill="both",
        expand=True,
    )

    header = tk.Frame(
        shell,
        bg=APP_BACKGROUND,
    )

    header.pack(fill="x")

    try:
        logo_image = tk.PhotoImage(
            file=IMAGE_PATH / "logo.png"
        )

        logo_image = logo_image.subsample(7, 7)

        logo = tk.Label(
            header,
            image=logo_image,
            bg=APP_BACKGROUND,
        )

        logo.image = logo_image
        logo.pack(pady=(14, 4))

    except Exception as ex:
        logger.warning("Logo image failed : %s", ex)

    tk.Label(
        header,
        text="Office Automation Suite - Karina",
        font=APP_TITLE_FONT,
        bg=APP_BACKGROUND,
        fg=PRIMARY_COLOR,
    ).pack(pady=(0, 2))

    tk.Label(
        header,
        text="OTO Finance",
        font=("Segoe UI", 11, "bold"),
        bg=APP_BACKGROUND,
        fg=APP_TEXT,
    ).pack(pady=(0, 2))

    tk.Label(
        header,
        text=f"Version {APP_VERSION}",
        font=("Segoe UI", 9),
        bg=APP_BACKGROUND,
        fg=APP_MUTED_TEXT,
    ).pack(pady=(0, 10))

    # =====================================================
    # Content
    # =====================================================

    content = tk.LabelFrame(
        shell,
        text="Automation Modules",
        font=APP_SECTION_FONT,
        padx=18,
        pady=16,
        bg=APP_PANEL,
        fg=PRIMARY_COLOR,
        bd=1,
        relief="solid",
        highlightbackground=APP_BORDER,
        highlightcolor=APP_ACCENT,
    )

    content.pack(
        fill="both",
        expand=True,
        padx=18,
        pady=(8, 14),
    )

    modules = [
        (
            "Attendance",
            "attendance.png",
            "Generate HRIS TXT and Excel report from attendance data.",
            True,
        ),
        (
            "Outlook",
            "outlook.png",
            "Process attendance revision emails and prepare HRIS TXT output.",
            True,
        ),
        (
            "HRIS",
            "hris.png",
            "Upload HRIS TXT files with configured Run Control IDs.",
            True,
        ),
        (
            "Utilities",
            "utilities.png",
            "Compare Attendance machine reports with Outlook revision reports.",
            True,
        ),
    ]

    images = []

    row = 0
    col = 0

    for module_name, image_file, description, is_available in modules:

        card = tk.Frame(
            content,
            bg=CARD_COLOR,
            bd=1,
            relief="solid",
            highlightbackground=BORDER_COLOR,
            highlightcolor=SECONDARY_COLOR,
        )

        card.grid(
            row=row,
            column=col,
            padx=16,
            pady=14,
            sticky="nsew",
        )

        try:

            image = tk.PhotoImage(
                file=IMAGE_PATH / image_file
            )

            image = image.subsample(6, 6)

            images.append(image)

            label = tk.Label(
                card,
                image=image,
                bg=CARD_COLOR,
            )

            label.pack(pady=(16, 8))

        except Exception:

            tk.Label(
                card,
                text="[ Image ]",
                bg=CARD_COLOR,
                fg=TEXT_SECONDARY,
                font=DEFAULT_FONT,
            ).pack(pady=(16, 8))

        tk.Label(
            card,
            text=module_name,
            bg=CARD_COLOR,
            fg=PRIMARY_COLOR,
            font=APP_CARD_TITLE_FONT,
        ).pack(pady=(0, 4))

        tk.Label(
            card,
            text=description,
            bg=CARD_COLOR,
            fg=TEXT_SECONDARY,
            font=DEFAULT_FONT,
            justify="center",
            wraplength=360,
        ).pack(
            fill="x",
            padx=18,
            pady=(0, 12),
        )

        module_commands = {
            "Attendance": partial(open_attendance_module, root),
            "Outlook": partial(open_outlook_module, root),
            "HRIS": partial(open_hris_module, root),
            "Utilities": partial(open_utilities_module, root),
        }
        button_command = module_commands.get(
            module_name,
            partial(coming_soon, module_name),
        )

        button_bg = APP_SUCCESS if is_available else APP_ACCENT
        button_active_bg = APP_SUCCESS_ACTIVE if is_available else PRIMARY_COLOR

        tk.Button(
            card,
            text=f"Open {module_name}" if is_available else module_name,
            width=18,
            font=BUTTON_FONT,
            bg=button_bg,
            fg="#FFFFFF",
            activebackground=button_active_bg,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            command=lambda m=module_name, c=button_command: launch_module(
                m,
                c,
            ),
        ).pack(
            pady=(0, 16),
            ipady=6,
        )

        col += 1

        if col > 1:
            col = 0
            row += 1

    content.columnconfigure(0, weight=1, uniform="module")
    content.columnconfigure(1, weight=1, uniform="module")
    content.rowconfigure(0, weight=1, uniform="module")
    content.rowconfigure(1, weight=1, uniform="module")

    # =====================================================
    # Footer
    # =====================================================

    footer = tk.Frame(
        root,
        bg=PRIMARY_COLOR,
        height=28,
    )

    footer.pack(
        side="bottom",
        fill="x",
    )

    tk.Label(
        footer,
        textvariable=status_var,
        bg=PRIMARY_COLOR,
        fg="#FFFFFF",
        font=DEFAULT_FONT,
        anchor="w",
    ).pack(
        side="left",
        padx=10,
    )

    tk.Label(
        footer,
        text="© 2026 OTO Finance",
        bg=PRIMARY_COLOR,
        fg="#DDEBFA",
        font=DEFAULT_FONT,
        anchor="e",
    ).pack(
        side="right",
        padx=10,
    )

    footer.winfo_children()[-1].config(
        text="(c) 2026 OTO Finance"
    )

    logger.info("Launcher loaded successfully.")

    root.mainloop()


if __name__ == "__main__":
    main()
