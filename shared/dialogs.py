"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : dialogs.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Centralized dialog service.

All message dialogs must go through this class.

=========================================================
"""

from __future__ import annotations

from tkinter import messagebox

from config.app_config import APP_NAME
from shared.logger import get_logger

logger = get_logger(__name__)


class Dialog:
    """
    Centralized dialog service.
    """

    @staticmethod
    def info(message: str, title: str | None = None) -> None:
        """
        Show information dialog.
        """

        dialog_title = title or APP_NAME

        logger.info(message)

        messagebox.showinfo(
            dialog_title,
            message,
        )

    @staticmethod
    def warning(message: str, title: str | None = None) -> None:
        """
        Show warning dialog.
        """

        dialog_title = title or APP_NAME

        logger.warning(message)

        messagebox.showwarning(
            dialog_title,
            message,
        )

    @staticmethod
    def error(message: str, title: str | None = None) -> None:
        """
        Show error dialog.
        """

        dialog_title = title or APP_NAME

        logger.error(message)

        messagebox.showerror(
            dialog_title,
            message,
        )

    @staticmethod
    def confirm(
        message: str,
        title: str | None = None,
    ) -> bool:
        """
        Show confirmation dialog.
        """

        dialog_title = title or APP_NAME

        logger.info(f"Confirmation requested: {message}")

        return messagebox.askyesno(
            dialog_title,
            message,
        )