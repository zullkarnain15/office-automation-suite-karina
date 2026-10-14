"""OAS-K UI8 retro theme foundation."""

from ui.theme.attendance_ot import (
    DEFAULT_ATTENDANCE_OT_THEME,
    AttendanceOTPalette,
    AttendanceOTTheme,
    AttendanceOTTypography,
    apply_attendance_ot_styles,
    resolve_attendance_ot_theme,
)
from ui.theme.font_loader import FontLoadResult, load_theme_fonts
from ui.theme.palette import RetroPalette, palette
from ui.theme.typography import RetroTypography, typography

__all__ = [
    "AttendanceOTPalette",
    "AttendanceOTTheme",
    "AttendanceOTTypography",
    "DEFAULT_ATTENDANCE_OT_THEME",
    "FontLoadResult",
    "RetroPalette",
    "RetroTypography",
    "apply_attendance_ot_styles",
    "load_theme_fonts",
    "palette",
    "typography",
    "resolve_attendance_ot_theme",
]
