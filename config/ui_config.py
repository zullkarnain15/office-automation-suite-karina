"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : ui_config.py
Module      : Configuration
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

User Interface configuration.

All visual appearance settings for OAS-K are defined here.

=========================================================
"""

# =========================================================
# WINDOW
# =========================================================

WINDOW_WIDTH: int = 1100
WINDOW_HEIGHT: int = 720

WINDOW_MIN_WIDTH: int = 1000
WINDOW_MIN_HEIGHT: int = 650

WINDOW_RESIZABLE: bool = False

# =========================================================
# HEADER
# =========================================================

HEADER_HEIGHT: int = 70

# =========================================================
# COLOR PALETTE
# =========================================================

PRIMARY_COLOR: str = "#003366"       # OTO Finance Blue
SECONDARY_COLOR: str = "#00509E"
SUCCESS_COLOR: str = "#2E8B57"
WARNING_COLOR: str = "#F4B400"
ERROR_COLOR: str = "#D32F2F"

BACKGROUND_COLOR: str = "#F5F7FA"
CARD_COLOR: str = "#FFFFFF"

TEXT_PRIMARY: str = "#222222"
TEXT_SECONDARY: str = "#666666"

BORDER_COLOR: str = "#D9D9D9"

# =========================================================
# FONT
# =========================================================

DEFAULT_FONT: tuple[str, int] = ("Segoe UI", 10)

TITLE_FONT: tuple[str, int, str] = (
    "Segoe UI",
    20,
    "bold",
)

HEADER_FONT: tuple[str, int, str] = (
    "Segoe UI",
    14,
    "bold",
)

SUBTITLE_FONT: tuple[str, int] = (
    "Segoe UI",
    10,
)

BUTTON_FONT: tuple[str, int, str] = (
    "Segoe UI",
    10,
    "bold",
)

LOG_FONT: tuple[str, int] = (
    "Consolas",
    10,
)

# =========================================================
# BUTTON
# =========================================================

BUTTON_WIDTH: int = 18
BUTTON_HEIGHT: int = 1

# =========================================================
# ICON
# =========================================================

ICON_SIZE_SMALL: int = 24
ICON_SIZE_MEDIUM: int = 32
ICON_SIZE_LARGE: int = 64

# =========================================================
# FRAME
# =========================================================

FRAME_PADDING: int = 15
SECTION_PADDING: int = 10

# =========================================================
# ENTRY
# =========================================================

ENTRY_WIDTH: int = 55

# =========================================================
# PROGRESS BAR
# =========================================================

PROGRESS_LENGTH: int = 650

# =========================================================
# PROCESS LOG
# =========================================================

LOG_HEIGHT: int = 12

# =========================================================
# STATUS BAR
# =========================================================

STATUS_HEIGHT: int = 24