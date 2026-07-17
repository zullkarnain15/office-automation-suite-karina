"""Utilities Hub with lazily loaded independent utility modules."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from config.app_config import UTILITIES_ICON
from shared.logger import get_logger

logger = get_logger(__name__)

APP_BACKGROUND = "#EAF2FA"
APP_PANEL = "#F8FBFF"
APP_BORDER = "#C7D5E6"
APP_TEXT = "#102A43"
APP_MUTED = "#60758A"
APP_PRIMARY = "#123B63"
APP_ACCENT = "#198FA3"
APP_SUCCESS = "#43A58F"


class UtilitiesGUI:
    """Landing page that keeps each utility isolated and lazy-loaded."""

    def __init__(self, root: tk.Tk | tk.Toplevel) -> None:
        self.root = root
        self.root.title("Utilities")
        self.root.geometry("900x500")
        self.root.minsize(820, 450)
        self.root.configure(bg=APP_BACKGROUND)
        try:
            self.root.iconbitmap(UTILITIES_ICON)
        except Exception:
            pass
        self._build()

    def _build(self) -> None:
        tk.Label(
            self.root,
            text="Utilities",
            font=("Segoe UI", 23, "bold"),
            bg=APP_BACKGROUND,
            fg=APP_PRIMARY,
        ).pack(pady=(24, 3))
        tk.Label(
            self.root,
            text="Pilih utility sesuai kebutuhan proses.",
            font=("Segoe UI", 10),
            bg=APP_BACKGROUND,
            fg=APP_MUTED,
        ).pack(pady=(0, 22))

        cards = tk.Frame(self.root, bg=APP_BACKGROUND)
        cards.pack(fill="both", expand=True, padx=32, pady=(0, 32))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.rowconfigure(0, weight=1)

        self._card(
            cards,
            0,
            "Comparison Result",
            (
                "Membandingkan report Attendance mesin dengan report "
                "Outlook-Revisi tanpa mengubah data sumber."
            ),
            "Open Comparison",
            self._open_reconciliation,
        )
        self._card(
            cards,
            1,
            "Attachment Consolidation",
            (
                "Memulihkan dan menggabungkan attachment Excel atau TXT "
                "menjadi file TXT HRIS yang tervalidasi."
            ),
            "Open Consolidation",
            self._open_consolidation,
        )

    def _card(
        self,
        parent: tk.Widget,
        column: int,
        title: str,
        description: str,
        button_text: str,
        command,
    ) -> None:
        card = tk.Frame(
            parent,
            bg=APP_PANEL,
            bd=1,
            relief="solid",
            highlightbackground=APP_BORDER,
        )
        card.grid(
            row=0,
            column=column,
            padx=12,
            pady=8,
            sticky="nsew",
        )
        tk.Label(
            card,
            text=title,
            font=("Segoe UI", 15, "bold"),
            bg=APP_PANEL,
            fg=APP_PRIMARY,
        ).pack(pady=(38, 14), padx=24)
        tk.Label(
            card,
            text=description,
            font=("Segoe UI", 10),
            bg=APP_PANEL,
            fg=APP_TEXT,
            justify="center",
            wraplength=310,
        ).pack(fill="x", padx=30)
        tk.Button(
            card,
            text=button_text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=APP_SUCCESS if column == 0 else APP_ACCENT,
            fg="white",
            activebackground=APP_PRIMARY,
            activeforeground="white",
            relief="flat",
            bd=0,
        ).pack(pady=(28, 32), ipadx=14, ipady=6)

    def _open_reconciliation(self) -> None:
        try:
            from utilities.attendance_reconciliation.gui import (
                AttendanceReconciliationGUI,
            )

            window = tk.Toplevel(self.root)
            window.transient(self.root)
            AttendanceReconciliationGUI(window)
            window.lift()
            window.focus_force()
            logger.info("Comparison Result utility opened.")
        except Exception as error:
            logger.exception("Comparison Result utility could not be opened.")
            messagebox.showerror(
                "Utilities",
                f"Gagal membuka Comparison Result.\n\n{error}",
                parent=self.root,
            )

    def _open_consolidation(self) -> None:
        try:
            from utilities.attachment_consolidation.gui import (
                AttachmentConsolidationGUI,
            )

            window = tk.Toplevel(self.root)
            window.transient(self.root)
            AttachmentConsolidationGUI(window)
            window.lift()
            window.focus_force()
            logger.info("Attachment Consolidation utility opened.")
        except Exception as error:
            logger.exception(
                "Attachment Consolidation utility could not be opened."
            )
            messagebox.showerror(
                "Utilities",
                f"Gagal membuka Attachment Consolidation.\n\n{error}",
                parent=self.root,
            )
