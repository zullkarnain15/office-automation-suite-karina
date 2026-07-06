"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : helpers.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

General helper functions.

Business logic is NOT allowed in this module.

=========================================================
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path


def ensure_directory(directory: Path) -> Path:
    """
    Create directory if it does not exist.

    Parameters
    ----------
    directory : Path

    Returns
    -------
    Path
    """

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def current_timestamp() -> str:
    """
    Return current timestamp.

    Format:
        YYYYMMDD_HHMMSS
    """

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_output_filename(
    prefix: str,
    extension: str,
) -> str:
    """
    Create output filename.

    Example
    -------
    Attendance_20260704_081500.txt
    """

    return f"{prefix}_{current_timestamp()}{extension}"


def format_file_size(size: int) -> str:
    """
    Convert bytes to readable size.
    """

    units = ["B", "KB", "MB", "GB"]

    value = float(size)

    for unit in units:

        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} TB"


def open_folder(path: Path) -> None:
    """
    Open folder using Windows Explorer.
    """

    subprocess.Popen(
        ["explorer", str(path)]
    )


def file_exists(path: Path) -> bool:
    """
    Check file existence.
    """

    return path.exists()


def folder_exists(path: Path) -> bool:
    """
    Check folder existence.
    """

    return path.exists() and path.is_dir()