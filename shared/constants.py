"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : constants.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Global constants shared across all modules.

=========================================================
"""

# =========================================================
# APPLICATION STATUS
# =========================================================

STATUS_READY: str = "Ready"
STATUS_RUNNING: str = "Running"
STATUS_SUCCESS: str = "Success"
STATUS_WARNING: str = "Warning"
STATUS_ERROR: str = "Error"
STATUS_FINISHED: str = "Finished"

# =========================================================
# PROCESS RESULT
# =========================================================

RESULT_SUCCESS: str = "SUCCESS"
RESULT_FAILED: str = "FAILED"
RESULT_CANCELLED: str = "CANCELLED"

# =========================================================
# LOG LEVEL
# =========================================================

LOG_DEBUG: str = "DEBUG"
LOG_INFO: str = "INFO"
LOG_WARNING: str = "WARNING"
LOG_ERROR: str = "ERROR"
LOG_CRITICAL: str = "CRITICAL"

# =========================================================
# FILE TYPES
# =========================================================

TEXT_FILE: str = "*.txt"
EXCEL_FILE: str = "*.xlsx"
MDB_FILE: str = "*.mdb"
ALL_FILES: str = "*.*"

# =========================================================
# MODULE NAME
# =========================================================

MODULE_MAIN: str = "Main"
MODULE_ATTENDANCE: str = "Attendance"
MODULE_OUTLOOK: str = "Outlook"
MODULE_HRIS: str = "HRIS"
MODULE_UTILITIES: str = "Utilities"

# =========================================================
# BUTTON LABEL
# =========================================================

BUTTON_BROWSE: str = "Browse..."
BUTTON_START: str = "Start"
BUTTON_PROCESS: str = "Process"
BUTTON_GENERATE: str = "Generate"
BUTTON_SAVE: str = "Save"
BUTTON_CLEAR: str = "Clear"
BUTTON_EXIT: str = "Exit"
BUTTON_CLOSE: str = "Close"

# =========================================================
# DIALOG TITLE
# =========================================================

DIALOG_INFO: str = "Information"
DIALOG_WARNING: str = "Warning"
DIALOG_ERROR: str = "Error"
DIALOG_CONFIRM: str = "Confirmation"

# =========================================================
# DATE & TIME
# =========================================================

DEFAULT_TIME: str = "00:00"

# =========================================================
# PROGRESS
# =========================================================

PROGRESS_MINIMUM: int = 0
PROGRESS_MAXIMUM: int = 100

# =========================================================
# TEXT ENCODING
# =========================================================

UTF8: str = "utf-8"
ANSI: str = "ansi"

# =========================================================
# EMPTY VALUE
# =========================================================

EMPTY: str = "" 