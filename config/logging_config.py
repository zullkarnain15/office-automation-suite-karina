"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : logging_config.py
Module      : Configuration
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Logging configuration for Office Automation Suite - Karina.

This module contains logging constants shared across the
entire application.

=========================================================
"""

from pathlib import Path

from config.app_config import LOG_PATH

# =========================================================
# LOG DIRECTORY
# =========================================================

LOG_DIRECTORY: Path = LOG_PATH

# =========================================================
# LOG FILE
# =========================================================

LOG_FILE_NAME: str = "oas_karina.log"

LOG_FILE_PATH: Path = LOG_DIRECTORY / LOG_FILE_NAME

# =========================================================
# LOGGING LEVEL
# =========================================================

LOG_LEVEL: str = "INFO"

# Available:
# DEBUG
# INFO
# WARNING
# ERROR
# CRITICAL

# =========================================================
# LOG FORMAT
# =========================================================

LOG_FORMAT: str = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)s | "
    "%(message)s"
)

DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# =========================================================
# ROTATING LOG CONFIGURATION
# =========================================================

ENABLE_ROTATING_LOG: bool = True

MAX_LOG_FILE_SIZE: int = 5 * 1024 * 1024
# 5 MB

BACKUP_LOG_COUNT: int = 5

# =========================================================
# CONSOLE LOG
# =========================================================

ENABLE_CONSOLE_LOG: bool = True

# =========================================================
# FILE LOG
# =========================================================

ENABLE_FILE_LOG: bool = True

# =========================================================
# GUI LOG
# =========================================================

ENABLE_GUI_LOG: bool = True

# =========================================================
# STARTUP
# =========================================================

CREATE_LOG_FOLDER_IF_NOT_EXISTS: bool = True