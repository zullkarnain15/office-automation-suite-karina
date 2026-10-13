"""Shared OAS-K default styles scoped to Finger Monitoring."""

from __future__ import annotations

from tkinter import ttk

from ui.theme.attendance_ot import resolve_attendance_ot_theme
from ui.theme.palette import palette


def apply_finger_monitoring_styles(root) -> ttk.Style:
    """Apply Finger Monitoring aliases without introducing a separate theme."""

    theme = resolve_attendance_ot_theme(root)
    colors, fonts = theme.palette, theme.typography
    style = ttk.Style(root)
    style.configure("FingerMonitoringPage.TFrame", background=colors.background)
    style.configure("FingerMonitoringSurface.TFrame", background=colors.surface)
    style.configure(
        "FingerMonitoringCard.TFrame",
        background=colors.card,
        bordercolor=colors.ink,
        relief="solid",
        borderwidth=1,
    )
    for name, color in (
        ("Title", colors.ink),
        ("Body", colors.ink),
        ("Muted", colors.chalk_muted),
    ):
        style.configure(
            f"FingerMonitoring{name}.TLabel",
            background=colors.surface,
            foreground=color,
            font=(fonts.ui_family, 10, "bold" if name == "Title" else "normal"),
        )
    style.configure(
        "FingerMonitoringCard.TLabel",
        background=colors.card,
        foreground=colors.ink,
        font=(fonts.ui_family, 10),
    )
    style.configure(
        "FingerMonitoringProgress.TLabel",
        background=colors.surface,
        foreground=colors.ink,
        font=(fonts.ui_family, 8, "bold"),
    )
    style.configure("FingerMonitoring.TNotebook", background=colors.surface)
    style.configure(
        "FingerMonitoring.TNotebook.Tab",
        background=colors.card,
        foreground=colors.ink,
        font=(fonts.heading_family, 9, "bold"),
        padding=(12, 7),
    )
    style.map(
        "FingerMonitoring.TNotebook.Tab",
        background=[("selected", colors.selection), ("active", colors.chalk_blue)],
        foreground=[("selected", colors.chalk_white)],
    )
    for name, background in (
        ("FingerMonitoring", colors.filter_mint),
        ("FingerMonitoringMint", colors.filter_mint),
        ("FingerMonitoringPink", colors.filter_pink),
        ("FingerMonitoringPurple", colors.filter_purple),
        ("FingerMonitoringYellow", colors.tab_yellow),
        ("FingerMonitoringOrange", colors.tab_orange),
    ):
        style.configure(
            f"{name}.TButton",
            background=background,
            foreground=colors.chalk_white,
            bordercolor=colors.ink,
            font=(fonts.heading_family, 9, "bold"),
            padding=(9, 6),
        )
        style.map(
            f"{name}.TButton",
            background=[("pressed", colors.selection), ("active", background)],
            foreground=[("active", colors.chalk_white)],
        )
    style.configure(
        "FingerMonitoringDanger.TButton",
        background=palette.danger_red,
        foreground=colors.chalk_white,
        bordercolor=colors.ink,
        font=(fonts.heading_family, 9, "bold"),
        padding=(9, 6),
    )
    style.map(
        "FingerMonitoringDanger.TButton",
        background=[("pressed", colors.selection), ("active", palette.danger_red)],
        foreground=[("active", colors.chalk_white)],
    )
    style.configure(
        "FingerMonitoring.Horizontal.TProgressbar",
        background=colors.filter_mint,
        troughcolor=colors.card,
        bordercolor=colors.ink,
        lightcolor=colors.filter_mint,
        darkcolor=colors.filter_mint,
        thickness=14,
    )
    style.configure(
        "FingerMonitoring.Treeview",
        background=colors.card,
        fieldbackground=colors.card,
        foreground=colors.ink,
        rowheight=24,
        font=(fonts.ui_family, 9),
    )
    style.map(
        "FingerMonitoring.Treeview",
        background=[("selected", colors.selection)],
        foreground=[("selected", colors.chalk_white)],
    )
    style.configure(
        "FingerMonitoring.Treeview.Heading",
        background=colors.selection,
        foreground=colors.chalk_white,
        font=(fonts.heading_family, 9, "bold"),
    )
    return style
