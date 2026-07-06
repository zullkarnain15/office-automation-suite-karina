"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : validators.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Shared validation utilities.

Business validation is NOT allowed in this module.

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


# =========================================================
# VALIDATION RESULT
# =========================================================

@dataclass(slots=True)
class ValidationResult:
    """
    Standard validation result.
    """

    valid: bool
    message: str = ""
    value: Any = None


# =========================================================
# FACTORY FUNCTIONS
# =========================================================

def success(value: Any = None) -> ValidationResult:
    """
    Create successful validation result.
    """

    return ValidationResult(
        valid=True,
        message="",
        value=value,
    )


def failure(message: str) -> ValidationResult:
    """
    Create failed validation result.
    """

    return ValidationResult(
        valid=False,
        message=message,
    )


# =========================================================
# FOLDER
# =========================================================

def validate_folder(path: str | Path) -> ValidationResult:
    """
    Validate folder.
    """

    folder = Path(path)

    if not folder.exists():
        return failure("Folder does not exist.")

    if not folder.is_dir():
        return failure("Selected path is not a folder.")

    return success(folder)


# =========================================================
# FILE
# =========================================================

def validate_file(path: str | Path) -> ValidationResult:
    """
    Validate file.
    """

    file = Path(path)

    if not file.exists():
        return failure("File does not exist.")

    if not file.is_file():
        return failure("Selected path is not a file.")

    return success(file)


# =========================================================
# FILE EXTENSION
# =========================================================

def validate_extension(
    path: str | Path,
    extensions: tuple[str, ...],
) -> ValidationResult:
    """
    Validate file extension.
    """

    file = Path(path)

    if file.suffix.lower() not in extensions:
        return failure(
            f"Unsupported file type: {file.suffix}"
        )

    return success(file)


# =========================================================
# EMPTY TEXT
# =========================================================

def validate_required(text: str) -> ValidationResult:
    """
    Validate required text.
    """

    if not text.strip():
        return failure("Required field is empty.")

    return success(text)