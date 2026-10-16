"""Retro platformer-inspired styles scoped to Finger Monitoring only."""

from __future__ import annotations

from tkinter import ttk

from ui.theme.attendance_ot import resolve_attendance_ot_theme


class FingerMonitoringPalette:
    """High-contrast colors inspired by classic 8-bit platform games."""

    sky = "#CFEFFF"
    sky_light = "#EAF8FF"
    cloud = "#FFFDF4"
    brick = "#A33B20"
    brick_pressed = "#742615"
    block_gold = "#E7A900"
    block_gold_pressed = "#B87800"
    pipe_green = "#287B42"
    pipe_green_pressed = "#1A542C"
    royal_blue = "#2255B5"
    royal_blue_pressed = "#173B82"
    orange = "#B24B18"
    danger = "#B3261E"
    ink = "#24150D"
    muted = "#5D5149"
    white = "#FFFFFF"


finger_palette = FingerMonitoringPalette()


def apply_finger_monitoring_styles(root) -> ttk.Style:
    """Apply an accessible, restrained 8-bit theme to this module."""

    theme = resolve_attendance_ot_theme(root)
    fonts = theme.typography
    colors = finger_palette
    style = ttk.Style(root)
    style.configure("FingerMonitoringPage.TFrame", background=colors.sky)
    style.configure("FingerMonitoringSurface.TFrame", background=colors.sky_light)
    style.configure(
        "FingerMonitoringCard.TFrame",
        background=colors.cloud,
        bordercolor=colors.ink,
        relief="solid",
        borderwidth=2,
    )
    for name, color in (
        ("Title", colors.ink),
        ("Body", colors.ink),
        ("Muted", colors.muted),
    ):
        style.configure(
            f"FingerMonitoring{name}.TLabel",
            background=colors.sky_light,
            foreground=color,
            font=(fonts.ui_family, 10, "bold" if name == "Title" else "normal"),
        )
    style.configure(
        "FingerMonitoringCard.TLabel",
        background=colors.cloud,
        foreground=colors.ink,
        font=(fonts.ui_family, 10),
    )
    for name, background in (
        ("Total", colors.royal_blue),
        ("Online", colors.pipe_green),
        ("Offline", colors.orange),
        ("Alert", colors.danger),
    ):
        style.configure(
            f"FingerMonitoring{name}Card.TFrame",
            background=background,
            bordercolor=colors.ink,
            relief="solid",
            borderwidth=2,
        )
        style.configure(
            f"FingerMonitoring{name}Card.TLabel",
            background=background,
            foreground=colors.white,
            font=(fonts.ui_family, 10),
        )
    style.configure(
        "FingerMonitoringProgress.TLabel",
        background=colors.sky_light,
        foreground=colors.ink,
        font=(fonts.ui_family, 8, "bold"),
    )
    style.configure("FingerMonitoring.TNotebook", background=colors.sky_light)
    style.configure(
        "FingerMonitoring.TNotebook.Tab",
        background=colors.cloud,
        foreground=colors.ink,
        font=(fonts.heading_family, 9, "bold"),
        padding=(12, 7),
    )
    style.map(
        "FingerMonitoring.TNotebook.Tab",
        background=[("selected", colors.brick), ("active", colors.block_gold)],
        foreground=[("selected", colors.white), ("active", colors.ink)],
    )
    for name, background, pressed, foreground in (
        ("FingerMonitoring", colors.pipe_green, colors.pipe_green_pressed, colors.white),
        ("FingerMonitoringMint", colors.pipe_green, colors.pipe_green_pressed, colors.white),
        ("FingerMonitoringPink", colors.brick, colors.brick_pressed, colors.white),
        ("FingerMonitoringPurple", colors.royal_blue, colors.royal_blue_pressed, colors.white),
        ("FingerMonitoringYellow", colors.block_gold, colors.block_gold_pressed, colors.ink),
        ("FingerMonitoringOrange", colors.orange, colors.brick_pressed, colors.white),
    ):
        style.configure(
            f"{name}.TButton",
            background=background,
            foreground=foreground,
            bordercolor=colors.ink,
            font=(fonts.heading_family, 9, "bold"),
            padding=(9, 6),
        )
        style.map(
            f"{name}.TButton",
            background=[("pressed", pressed), ("active", pressed)],
            foreground=[("active", foreground)],
        )
    style.configure(
        "FingerMonitoringDanger.TButton",
        background=colors.danger,
        foreground=colors.white,
        bordercolor=colors.ink,
        font=(fonts.heading_family, 9, "bold"),
        padding=(9, 6),
    )
    style.map(
        "FingerMonitoringDanger.TButton",
        background=[("pressed", colors.brick_pressed), ("active", colors.brick_pressed)],
        foreground=[("active", colors.white)],
    )
    style.configure(
        "FingerMonitoring.Horizontal.TProgressbar",
        background=colors.block_gold,
        troughcolor=colors.cloud,
        bordercolor=colors.ink,
        lightcolor=colors.block_gold,
        darkcolor=colors.block_gold,
        thickness=14,
    )
    style.configure(
        "FingerMonitoring.Treeview",
        background=colors.cloud,
        fieldbackground=colors.cloud,
        foreground=colors.ink,
        rowheight=24,
        font=(fonts.ui_family, 9),
    )
    style.map(
        "FingerMonitoring.Treeview",
        background=[("selected", colors.royal_blue)],
        foreground=[("selected", colors.white)],
    )
    style.configure(
        "FingerMonitoring.Treeview.Heading",
        background=colors.royal_blue,
        foreground=colors.white,
        font=(fonts.heading_family, 9, "bold"),
    )
    style.configure(
        "FingerMonitoring.TEntry",
        fieldbackground=colors.cloud,
        foreground=colors.ink,
        bordercolor=colors.royal_blue,
        insertcolor=colors.ink,
        font=(fonts.ui_family, 9),
    )
    style.configure(
        "FingerMonitoring.TCombobox",
        fieldbackground=colors.cloud,
        background=colors.cloud,
        foreground=colors.ink,
        bordercolor=colors.royal_blue,
        arrowcolor=colors.royal_blue,
        font=(fonts.ui_family, 9),
    )
    style.map(
        "FingerMonitoring.TCombobox",
        fieldbackground=[("readonly", colors.cloud)],
        background=[("active", colors.sky_light)],
        foreground=[("disabled", colors.muted)],
    )
    return style
