"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : app_config.py
Module      : Configuration
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Global application configuration.

This module contains application-wide constants that are
shared across all OAS-K modules.

=========================================================
"""

from pathlib import Path

# =========================================================
# APPLICATION INFORMATION
# =========================================================

APP_NAME: str = "OAS-K"
APP_FULL_NAME: str = "Office Automation Suite - Karina"
COMPANY_NAME: str = "OTO Finance"

APP_VERSION: str = "1.0.0"
APP_STATUS: str = "Development"
BUILD_NUMBER: str = "001"

WINDOW_TITLE: str = (
    f"{APP_NAME} | {APP_FULL_NAME} | {COMPANY_NAME}"
)

# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# =========================================================
# APPLICATION PATHS
# =========================================================

ASSETS_PATH: Path = PROJECT_ROOT / "assets"

ICON_PATH: Path = ASSETS_PATH / "icons"
IMAGE_PATH: Path = ASSETS_PATH / "images"
TEMPLATE_PATH: Path = ASSETS_PATH / "templates"
THEME_PATH: Path = ASSETS_PATH / "themes"
FONT_PATH: Path = ASSETS_PATH / "fonts"

CONFIG_PATH: Path = PROJECT_ROOT / "config"

LOG_PATH: Path = PROJECT_ROOT / "logs"
OUTPUT_PATH: Path = PROJECT_ROOT / "output"
TEMP_PATH: Path = PROJECT_ROOT / "temp"
DOCS_PATH: Path = PROJECT_ROOT / "docs"

# =========================================================
# DEFAULT ICONS
# =========================================================

APP_ICON: Path = ICON_PATH / "app.ico"
LOGO_ICON: Path = ICON_PATH / "logo.ico"

ATTENDANCE_ICON: Path = ICON_PATH / "attendance.ico"
OUTLOOK_ICON: Path = ICON_PATH / "outlook.ico"
HRIS_ICON: Path = ICON_PATH / "hris.ico"
UTILITIES_ICON: Path = ICON_PATH / "utilities.ico"

# =========================================================
# ATTENDANCE MODULE
# =========================================================

ATTENDANCE_OUTPUT_EXTENSION: str = ".txt"

DEFAULT_OUTPUT_FILENAME: str = "Attendance"

SUPPORTED_DATABASE_EXTENSION: tuple[str, ...] = (
    ".mdb",
)

# =========================================================
# EXPORT
# =========================================================

TEXT_ENCODING: str = "utf-8"

CSV_DELIMITER: str = ","

TEXT_QUALIFIER: str = '"'

# =========================================================
# HRIS DATE/TIME FORMAT (DO NOT CHANGE)
# =========================================================

DATE_FORMAT: str = "%m/%d/%Y"

TIME_FORMAT: str = "%H:%M"

DATETIME_FORMAT: str = "%m/%d/%Y %H:%M"

# =========================================================
# APPLICATION FLAGS
# =========================================================

DEBUG: bool = False

TESTING: bool = False