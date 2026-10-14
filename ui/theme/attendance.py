"""Retro platformer styles scoped to the Attendance page."""

from __future__ import annotations

from tkinter import ttk

from ui.theme.attendance_ot import DEFAULT_ATTENDANCE_OT_THEME


def apply_attendance_styles(root) -> ttk.Style:
    """Apply readable, module-local retro styles without changing workflow UI."""

    colors = DEFAULT_ATTENDANCE_OT_THEME.palette
    fonts = DEFAULT_ATTENDANCE_OT_THEME.typography
    style = ttk.Style(root)
    style.configure("AttendancePage.TFrame", background=colors.background)
    style.configure("AttendanceSurface.TFrame", background=colors.surface)
    style.configure("AttendancePanel.TFrame", background=colors.card, bordercolor=colors.ink, relief="solid", borderwidth=2)
    style.configure("AttendanceBody.TFrame", background=colors.card)
    style.configure("AttendanceTitle.TLabel", background=colors.card, foreground=colors.ink, font=(fonts.ui_family, 10, "bold"))
    style.configure("AttendanceText.TLabel", background=colors.card, foreground=colors.ink, font=(fonts.ui_family, 9))
    for name, background, foreground in (("Attendance.TButton", colors.filter_mint, colors.chalk_white), ("AttendanceSecondary.TButton", colors.filter_blue, colors.chalk_white), ("AttendanceUtility.TButton", colors.tab_yellow, colors.chalk_white), ("AttendancePrimary.TButton", colors.tab_sage, colors.chalk_white), ("AttendanceDanger.TButton", colors.filter_pink, colors.chalk_white)):
        style.configure(name, background=background, foreground=foreground, bordercolor=colors.ink, font=(fonts.ui_family, 8, "bold"), padding=(7, 4))
        style.map(name, background=[("pressed", colors.selection), ("active", background)], foreground=[("disabled", colors.chalk_muted)])
    return style
