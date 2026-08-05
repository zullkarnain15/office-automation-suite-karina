"""Stable source contract constants for Att Data Repair."""

from __future__ import annotations

from datetime import time

FEATURE_NAME = "Att Data Repair"
FEATURE_FOLDER_NAME = "Att_Data_Repair"
TXT_FILENAME_PREFIX = "Att_Data_Repair"
REPORT_FILENAME_PREFIX = "Att_Data_Repair_Report"
ENGINE_VERSION = "1.0.0"
SUMMARY_SCHEMA_VERSION = 1

VALID_RECORDS_SHEET = "Valid_Records"
INVALID_RECORDS_SHEET = "Invalid_Records"
REQUIRED_SHEETS = (VALID_RECORDS_SHEET, INVALID_RECORDS_SHEET)

VALID_RECORDS_COLUMNS = (
    "No",
    "Source_File",
    "Relative_Path",
    "Source_Row",
    "Workflow",
    "NIK",
    "Date_In",
    "Time_In",
    "Date_Out",
    "Time_Out",
    "Output_TXT",
    "Status",
)

INVALID_RECORDS_COLUMNS = (
    "No",
    "Source_File",
    "Relative_Path",
    "Source_Row",
    "Workflow",
    "NIK",
    "Date_In",
    "Time_In",
    "Date_Out",
    "Time_Out",
    "Status_Code",
    "Reason",
    "Raw_Value",
)

SPREADSHEET_ERRORS = frozenset(
    {
        "#REF!",
        "#VALUE!",
        "#N/A",
        "#NAME?",
        "#DIV/0!",
        "#NUM!",
        "#NULL!",
    }
)

WORKFLOW_HO = "HO"
WORKFLOW_BRANCH = "Branch"
VALID_WORKFLOWS = (WORKFLOW_HO, WORKFLOW_BRANCH)
REPORT_SHEET_ORDER = (
    "Guide_Status",
    "Process_Summary",
    "Summary_Per_Karyawan",
    "Final_Records",
    "Changed_Records",
    "Anomaly",
    "Change_Log",
    "Source_Inventory",
)

DEFAULT_MINIMUM_DURATION_MINUTES = 61
DEFAULT_TXT_MAX_ROWS_PER_FILE = 10_000
TXT_UNIQUE_CODE_MIN = 1000
TXT_UNIQUE_CODE_MAX = 9999
WEEKDAY_DEFAULT_IN = time(9, 30)
WEEKDAY_DEFAULT_OUT = time(17, 0)
SATURDAY_DEFAULT_IN = time(9, 30)
SATURDAY_DEFAULT_OUT = time(12, 5)
SATURDAY_MISSING_OUT_DEFAULT = time(11, 0)
SUNDAY_INVALID_DEFAULT_IN = time(9, 30)
SUNDAY_INVALID_DEFAULT_OUT = time(12, 5)
MIDNIGHT_TIME_OUT_DEFAULT = time(23, 59)
