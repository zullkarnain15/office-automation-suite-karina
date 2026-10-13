"""Default OAS-K visual tokens scoped to the ATT & OT page."""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from ui.theme.font_loader import font_available, load_theme_fonts
from ui.theme.palette import palette


@dataclass(frozen=True)
class AttendanceOTPalette:
    """Compatibility names mapped to the application's shared default palette."""

    background: str = palette.soft_background
    surface: str = palette.soft_background
    card: str = palette.ivory_white
    selection: str = palette.royal_blue
    chalk_white: str = palette.ivory_white
    chalk_muted: str = palette.text_secondary
    chalk_yellow: str = palette.old_gold
    chalk_blue: str = palette.sky_blue
    chalk_pink: str = palette.danger_red
    tab_sage: str = palette.royal_blue
    tab_mint: str = palette.teal
    tab_pink: str = palette.danger_red
    tab_blue: str = palette.sky_blue
    tab_yellow: str = palette.old_gold
    tab_purple: str = palette.royal_blue
    tab_orange: str = palette.old_gold
    filter_mint: str = palette.teal
    filter_pink: str = palette.danger_red
    filter_blue: str = palette.sky_blue
    filter_purple: str = palette.royal_blue
    ink: str = palette.outline

    @property
    def tab_colors(self) -> tuple[str, ...]:
        return (self.tab_sage,) * 6


@dataclass(frozen=True)
class AttendanceOTTypography:
    """Resolved typefaces supplied by the shared OAS-K theme."""

    display_family: str = "Segoe UI"
    heading_family: str = "Segoe UI"
    ui_family: str = "Segoe UI"
    mono_family: str = "Consolas"


@dataclass(frozen=True)
class AttendanceOTTheme:
    palette: AttendanceOTPalette
    typography: AttendanceOTTypography

    @property
    def body_font(self) -> tuple[str, int]:
        return (self.typography.ui_family, 9)

    @property
    def body_bold_font(self) -> tuple[str, int, str]:
        return (self.typography.ui_family, 9, "bold")

    @property
    def heading_font(self) -> tuple[str, int, str]:
        """Use the readable body face for dashboard headings and labels."""
        return (self.typography.ui_family, 10, "bold")

    @property
    def display_font(self) -> tuple[str, int, str]:
        return (self.typography.display_family, 16, "bold")

    @property
    def table_font(self) -> tuple[str, int]:
        return (self.typography.ui_family, 9)

    @property
    def table_heading_font(self) -> tuple[str, int, str]:
        return (self.typography.heading_family, 9, "bold")


DEFAULT_ATTENDANCE_OT_THEME = AttendanceOTTheme(
    palette=AttendanceOTPalette(),
    typography=AttendanceOTTypography(),
)


def resolve_attendance_ot_theme(
    root: tk.Misc,
    _assets_path=None,
    *,
    logger: logging.Logger | None = None,
) -> AttendanceOTTheme:
    """Use the same process-scoped fonts and fallbacks as the rest of OAS-K."""

    fonts = load_theme_fonts(logger=logger)
    body_family = "Segoe UI" if font_available("Segoe UI", root) else fonts.ui_family
    return AttendanceOTTheme(
        DEFAULT_ATTENDANCE_OT_THEME.palette,
        AttendanceOTTypography(
            display_family=body_family,
            heading_family=fonts.ui_family,
            ui_family=body_family,
            mono_family=fonts.mono_family,
        ),
    )


def apply_attendance_ot_styles(root: tk.Misc, theme: AttendanceOTTheme) -> ttk.Style:
    """Apply ATT & OT aliases using the shared default OAS-K visual language."""

    colors = theme.palette
    fonts = theme.typography
    style = ttk.Style(root)
    style.configure("AttendanceOTPage.TFrame", background=colors.background)
    style.configure("AttendanceOTSurface.TFrame", background=colors.surface)
    style.configure("AttendanceOTCard.TFrame", background=colors.card, bordercolor=colors.ink, relief="solid", borderwidth=1)
    style.configure("AttendanceOT.TNotebook", background=colors.surface)
    style.configure("AttendanceOT.TNotebook.Tab", background=colors.card, foreground=colors.ink, font=(fonts.ui_family, 9, "bold"), padding=(12, 7))
    style.map(
        "AttendanceOT.TNotebook.Tab",
        background=[("selected", colors.tab_yellow), ("active", colors.chalk_blue)],
        foreground=[
            ("selected", colors.ink),
            ("active", colors.ink),
            ("!selected", colors.ink),
        ],
    )
    for name, size, weight, color in (("Title", 14, "bold", colors.ink), ("Body", 10, "normal", colors.ink), ("Status", 9, "normal", colors.chalk_muted)):
        style.configure(f"AttendanceOT{name}.TLabel", background=colors.surface, foreground=color, font=(fonts.ui_family, size, weight))
    style.configure("AttendanceOTCardBody.TLabel", background=colors.card, foreground=colors.ink, font=(fonts.ui_family, 10))
    style.configure("AttendanceOTPageStatus.TLabel", background=colors.background, foreground=colors.chalk_muted, font=(fonts.ui_family, 9))
    style.configure("AttendanceOTProgress.TLabel", background=colors.surface, foreground=colors.ink, font=(fonts.ui_family, 9, "bold"))
    for style_name, color in (("AttendanceOTDataUpdatePending.TLabel", colors.chalk_muted), ("AttendanceOTDataUpdateComplete.TLabel", colors.filter_mint), ("AttendanceOTDataUpdateError.TLabel", colors.filter_pink)):
        style.configure(style_name, background=colors.surface, foreground=color, font=(fonts.ui_family, 9, "bold"))
    for name, color in (("AttendanceOT", colors.chalk_blue), ("AttendanceOTSuccess", colors.filter_mint), ("AttendanceOTError", colors.filter_pink)):
        style.configure(f"{name}.Horizontal.TProgressbar", background=color, troughcolor=colors.card, bordercolor=colors.ink, lightcolor=color, darkcolor=color)
    style.configure("AttendanceOT.TButton", background=colors.filter_mint, foreground=colors.chalk_white, bordercolor=colors.ink, font=(fonts.heading_family, 9, "bold"), padding=(9, 6))
    style.map("AttendanceOT.TButton", background=[("pressed", colors.selection), ("active", palette.teal_hover)], foreground=[("active", colors.chalk_white)])
    for style_name, color in (("AttendanceOTFilterBranch.TButton", colors.filter_mint), ("AttendanceOTFilterPayGroup.TButton", colors.filter_pink), ("AttendanceOTFilterDepartment.TButton", colors.filter_blue), ("AttendanceOTFilterDivision.TButton", colors.filter_purple), ("AttendanceOTDataUpdateEmployee.TButton", colors.tab_mint), ("AttendanceOTDataUpdateSchedule.TButton", colors.tab_yellow), ("AttendanceOTDataUpdateAttendance.TButton", colors.tab_blue), ("AttendanceOTDataUpdateAll.TButton", colors.tab_orange), ("AttendanceOTApply.TButton", colors.filter_mint), ("AttendanceOTReset.TButton", colors.filter_pink)):
        style.configure(style_name, background=color, foreground=colors.chalk_white, bordercolor=colors.ink, font=(fonts.heading_family, 9, "bold"), padding=(9, 6))
        style.map(style_name, background=[("pressed", colors.selection), ("active", color)], foreground=[("active", colors.chalk_white)])
    style.configure("AttendanceOT.TEntry", fieldbackground=colors.card, foreground=colors.ink, bordercolor=colors.ink, lightcolor=colors.ink, darkcolor=colors.ink, insertcolor=colors.ink, font=(fonts.ui_family, 9))
    style.configure("AttendanceOT.TCombobox", fieldbackground=colors.card, background=colors.card, foreground=colors.ink, bordercolor=colors.ink, arrowcolor=colors.ink, font=(fonts.ui_family, 9))
    style.map("AttendanceOT.TCombobox", fieldbackground=[("readonly", colors.card)], background=[("active", colors.surface)], foreground=[("disabled", colors.chalk_muted)])
    style.configure("AttendanceOT.Treeview", background=colors.card, fieldbackground=colors.card, foreground=colors.ink, font=(fonts.ui_family, 9), rowheight=25)
    style.map("AttendanceOT.Treeview", background=[("selected", colors.selection)], foreground=[("selected", colors.chalk_white)])
    style.configure("AttendanceOT.Treeview.Heading", background=colors.selection, foreground=colors.chalk_white, font=(fonts.heading_family, 9, "bold"))
    style.configure(
        "AttendanceOTDetail.TFrame",
        background=colors.card,
        bordercolor=colors.ink,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "AttendanceOTDetail.Treeview",
        background=colors.card,
        fieldbackground=colors.card,
        foreground=colors.ink,
        bordercolor=colors.ink,
        relief="solid",
        borderwidth=1,
        font=(fonts.ui_family, 9),
        rowheight=25,
    )
    style.map(
        "AttendanceOTDetail.Treeview",
        background=[("selected", colors.selection)],
        foreground=[("selected", colors.chalk_white)],
    )
    style.configure(
        "AttendanceOTDetail.Treeview.Heading",
        background=colors.selection,
        foreground=colors.chalk_white,
        bordercolor=colors.ink,
        relief="solid",
        borderwidth=1,
        font=(fonts.heading_family, 9, "bold"),
    )
    return style
