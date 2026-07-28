"""Visual and window constants for the lightweight OAS-K UI shell."""

from __future__ import annotations

from ui.theme.palette import palette
from ui.theme.typography import typography

APP_TITLE = "Office Automation Suite – Karina by. ZSH"
DEFAULT_PAGE_ID = "dashboard"

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 640
SIDEBAR_WIDTH = 170

# UI7B.1 compact operational spacing. Existing page spacing remains stable.
COMPACT_SPACE_XS = 4
COMPACT_SPACE_SM = 6
COMPACT_SPACE_MD = 10
COMPACT_SPACE_LG = 14
COMPACT_SPACE_XL = 18

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

OUTLINE = palette.outline
ROYAL_BLUE = palette.royal_blue
SKY_BLUE = palette.sky_blue
SKY_BLUE_SOFT = palette.sky_blue_soft
SKY_BLUE_BORDER = palette.sky_blue_border
OPTION_CHIP_SELECTED_BACKGROUND = "#B7D4F2"
OPTION_CHIP_SELECTED_FOREGROUND = "#1F4E79"
OPTION_CHIP_SELECTED_BORDER = "#1F4E79"
FOREST_GREEN = palette.forest_green
OLD_GOLD = palette.old_gold
IVORY_WHITE = palette.ivory_white
SOFT_BACKGROUND = palette.soft_background
DANGER_RED = palette.danger_red

NAVY_DARK = OUTLINE
NAVY = ROYAL_BLUE
TEAL = OLD_GOLD
TEAL_DARK = "#7C5A2B"
GREEN_ACTION = FOREST_GREEN
BACKGROUND = SOFT_BACKGROUND
CONTENT_BACKGROUND = SOFT_BACKGROUND
CARD_BACKGROUND = IVORY_WHITE
TEXT_PRIMARY = OUTLINE
TEXT_SECONDARY = palette.text_secondary
BORDER = OUTLINE
LOG_BACKGROUND = palette.log_background
COMPACT_LOG_BACKGROUND = palette.log_background
LOG_TEXT = palette.log_text
INFO = ROYAL_BLUE

# Backward-compatible aliases used by the UI1-UI5 shell.
MAIN_HEADER = OUTLINE
PRIMARY_ACTION = GREEN_ACTION
MAIN_BACKGROUND = CONTENT_BACKGROUND
SIDEBAR_BACKGROUND = OUTLINE
SIDEBAR_ACTIVE = ROYAL_BLUE
SIDEBAR_HOVER = "#343050"
SUCCESS = GREEN_ACTION
WARNING = OLD_GOLD
ERROR = DANGER_RED
WHITE = IVORY_WHITE

FONT_FAMILY = typography.ui_family
FONT_FALLBACK = typography.ui_fallback
DISPLAY_FONT_FAMILY = typography.display_family
MONO_FONT_FAMILY = typography.mono_family
DEFAULT_FONT = (FONT_FAMILY, 9)
SMALL_FONT = (FONT_FAMILY, 8)
SECONDARY_FONT = (FONT_FAMILY, 8)
BUTTON_FONT = (FONT_FAMILY, 8, "bold")
APP_TITLE_FONT = (DISPLAY_FONT_FAMILY, 12)
PAGE_TITLE_FONT = (FONT_FAMILY, 15, "bold")
SECTION_TITLE_FONT = (FONT_FAMILY, 10, "bold")
CARD_TITLE_FONT = (FONT_FAMILY, 10, "bold")
CARD_BODY_FONT = (FONT_FAMILY, 9)
CARD_VALUE_FONT = (FONT_FAMILY, 13, "bold")
LOG_FONT = (MONO_FONT_FAMILY, 12)

PAGE_ORDER = (
    "dashboard",
    "attendance",
    "outlook_revisi",
    "hris",
    "utilities",
    "history",
    "settings",
    "system_health",
)
