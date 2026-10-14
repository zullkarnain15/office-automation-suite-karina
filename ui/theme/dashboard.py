"""Retro platformer styles scoped to the Dashboard page."""

from __future__ import annotations

from tkinter import ttk

from ui.theme.attendance_ot import DEFAULT_ATTENDANCE_OT_THEME


def apply_dashboard_styles(root) -> ttk.Style:
    """Apply high-contrast Dashboard-only styles."""

    colors = DEFAULT_ATTENDANCE_OT_THEME.palette
    fonts = DEFAULT_ATTENDANCE_OT_THEME.typography
    style = ttk.Style(root)
    style.configure("DashboardPage.TFrame", background=colors.background)
    style.configure("DashboardSurface.TFrame", background=colors.surface)
    style.configure("DashboardCard.TFrame", background=colors.card, bordercolor=colors.ink, relief="solid", borderwidth=2)
    style.configure("DashboardShadow.TFrame", background=colors.tab_sage)
    style.configure("DashboardQuick.TFrame", background=colors.card, bordercolor=colors.ink, relief="solid", borderwidth=2)
    style.configure("DashboardTitle.TLabel", background=colors.tab_sage, foreground=colors.chalk_white, font=(fonts.ui_family, 10, "bold"), padding=(8, 4))
    style.configure("DashboardText.TLabel", background=colors.card, foreground=colors.ink, font=(fonts.ui_family, 9))
    style.configure("DashboardSection.TLabel", background=colors.surface, foreground=colors.ink, font=(fonts.ui_family, 10, "bold"))
    style.configure("Dashboard.TButton", background=colors.filter_mint, foreground=colors.chalk_white, bordercolor=colors.ink, font=(fonts.ui_family, 9, "bold"), padding=(9, 6))
    style.map("Dashboard.TButton", background=[("pressed", colors.selection), ("active", colors.tab_mint)], foreground=[("active", colors.chalk_white)])
    style.configure("Dashboard.Treeview", background=colors.card, fieldbackground=colors.card, foreground=colors.ink, rowheight=25, font=(fonts.ui_family, 9))
    style.map("Dashboard.Treeview", background=[("selected", colors.selection)], foreground=[("selected", colors.chalk_white)])
    style.configure("Dashboard.Treeview.Heading", background=colors.selection, foreground=colors.chalk_white, font=(fonts.ui_family, 9, "bold"))
    for name, foreground in (("DashboardValue.TLabel", colors.ink), ("DashboardValueBlink1.TLabel", colors.tab_sage), ("DashboardValueBlink2.TLabel", colors.tab_orange), ("DashboardValueBlink3.TLabel", colors.chalk_yellow), ("DashboardValueBlink4.TLabel", colors.tab_orange), ("DashboardValueBlink5.TLabel", colors.tab_sage)):
        style.configure(name, background=colors.card, foreground=foreground, font=(fonts.ui_family, 13, "bold"))
    return style
