"""Central ttk light-theme configuration."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import (
    BACKGROUND,
    BORDER,
    BUTTON_FONT,
    CARD_BODY_FONT,
    CARD_TITLE_FONT,
    CARD_VALUE_FONT,
    CARD_BACKGROUND,
    DEFAULT_FONT,
    ERROR,
    FOREST_GREEN,
    INFO,
    IVORY_WHITE,
    LOG_BACKGROUND,
    LOG_TEXT,
    MAIN_BACKGROUND,
    MAIN_HEADER,
    OLD_GOLD,
    PAGE_TITLE_FONT,
    ROYAL_BLUE,
    SECTION_TITLE_FONT,
    SIDEBAR_ACTIVE,
    SIDEBAR_BACKGROUND,
    SIDEBAR_HOVER,
    SKY_BLUE,
    SMALL_FONT,
    SUCCESS,
    TEAL,
    TEAL_HOVER,
    TEAL_PRESSED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    WHITE,
)
from ui.theme.font_loader import load_theme_fonts


class StyleManager:
    def apply(self, root: tk.Misc) -> ttk.Style:
        font_result = load_theme_fonts()
        ui_family = font_result.ui_family
        display_family = font_result.display_family
        default_font = (ui_family, DEFAULT_FONT[1], *DEFAULT_FONT[2:])
        small_font = (ui_family, SMALL_FONT[1], *SMALL_FONT[2:])
        button_font = (ui_family, BUTTON_FONT[1], *BUTTON_FONT[2:])
        page_title_font = (ui_family, PAGE_TITLE_FONT[1], *PAGE_TITLE_FONT[2:])
        section_title_font = (
            ui_family,
            SECTION_TITLE_FONT[1],
            *SECTION_TITLE_FONT[2:],
        )
        card_title_font = (ui_family, CARD_TITLE_FONT[1], *CARD_TITLE_FONT[2:])
        card_body_font = (ui_family, CARD_BODY_FONT[1], *CARD_BODY_FONT[2:])
        card_value_font = (ui_family, CARD_VALUE_FONT[1], *CARD_VALUE_FONT[2:])
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=default_font)
        style.configure("TFrame", background=MAIN_BACKGROUND)
        style.configure("TLabel", background=MAIN_BACKGROUND, foreground=TEXT_PRIMARY)
        style.configure(
            "TLabelframe",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=2,
        )
        style.configure(
            "TLabelframe.Label",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=section_title_font,
            padding=(8, 3),
        )
        style.configure("OASK.TFrame", background=MAIN_BACKGROUND)
        style.configure("PageBackground.TFrame", background=BACKGROUND)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BACKGROUND)
        style.configure("Header.TFrame", background=MAIN_HEADER)
        style.configure(
            "TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(9, 6),
            bordercolor=BORDER,
            borderwidth=2,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "TEntry",
            fieldbackground=IVORY_WHITE,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            insertcolor=TEXT_PRIMARY,
            padding=(7, 5),
        )
        style.configure(
            "TCombobox",
            fieldbackground=IVORY_WHITE,
            background=IVORY_WHITE,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            arrowcolor=OLD_GOLD,
            padding=(6, 4),
            font=default_font,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", IVORY_WHITE), ("disabled", "#D7D1C0")],
            background=[("active", "#F4E2B9"), ("readonly", IVORY_WHITE)],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "TCheckbutton",
            background=MAIN_BACKGROUND,
            foreground=TEXT_PRIMARY,
            focuscolor=OLD_GOLD,
            font=default_font,
        )
        style.map(
            "TCheckbutton",
            background=[("active", MAIN_BACKGROUND)],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "TRadiobutton",
            background=MAIN_BACKGROUND,
            foreground=TEXT_PRIMARY,
            focuscolor=OLD_GOLD,
            font=default_font,
        )
        style.map(
            "TRadiobutton",
            background=[("active", MAIN_BACKGROUND)],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "TScrollbar",
            background=OLD_GOLD,
            troughcolor=MAIN_HEADER,
            bordercolor=BORDER,
            arrowcolor=IVORY_WHITE,
            lightcolor=OLD_GOLD,
            darkcolor=OLD_GOLD,
            borderwidth=1,
        )
        style.map(
            "TScrollbar",
            background=[("active", "#E0B66D"), ("pressed", "#B78335")],
            arrowcolor=[("disabled", "#77716A")],
        )
        style.configure("RPGShadow.TFrame", background=BORDER)
        style.configure("RPGPanel.TFrame", background=CARD_BACKGROUND)
        style.configure("RPGTitleStrip.TFrame", background=MAIN_HEADER)
        style.configure("RPGAccent.TFrame", background=OLD_GOLD)
        style.configure(
            "ContentCard.TFrame",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=2,
        )
        style.configure(
            "ModernCard.TFrame",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=2,
        )
        style.configure("CardAccent.TFrame", background=OLD_GOLD)
        style.configure("CardBody.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "SettingsPanel.TLabelframe",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=2,
        )
        style.configure(
            "SettingsPanel.TLabelframe.Label",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=section_title_font,
            padding=(8, 3),
        )
        style.configure(
            "SettingsPanel.TCheckbutton",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=default_font,
        )
        style.configure(
            "LogPanel.TFrame",
            background=LOG_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "StatusBar.TFrame",
            background=MAIN_HEADER,
            bordercolor=OLD_GOLD,
            relief="solid",
            borderwidth=1,
        )

        style.configure(
            "SidebarBrand.TLabel",
            background=SIDEBAR_BACKGROUND,
            foreground=OLD_GOLD,
            font=(display_family, 11),
        )
        style.configure(
            "SidebarCaption.TLabel",
            background=SIDEBAR_BACKGROUND,
            foreground=IVORY_WHITE,
            font=small_font,
        )
        style.configure(
            "Sidebar.TButton",
            background=SIDEBAR_BACKGROUND,
            foreground=IVORY_WHITE,
            anchor="w",
            padding=(6, 7),
            borderwidth=1,
            bordercolor="#3B394A",
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=(ui_family, 8),
        )
        style.map(
            "Sidebar.TButton",
            background=[
                ("active", SIDEBAR_HOVER),
                ("pressed", SIDEBAR_ACTIVE),
                ("focus", SIDEBAR_HOVER),
            ],
        )
        style.configure(
            "SidebarActive.TButton",
            background=SIDEBAR_ACTIVE,
            foreground=IVORY_WHITE,
            anchor="w",
            padding=(6, 7),
            borderwidth=2,
            bordercolor=OLD_GOLD,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=(ui_family, 8, "bold"),
        )
        style.map(
            "SidebarActive.TButton",
            background=[
                ("active", SIDEBAR_ACTIVE),
                ("focus", SIDEBAR_ACTIVE),
            ],
        )

        style.configure(
            "PageTitle.TLabel",
            background=MAIN_HEADER,
            foreground=WHITE,
            font=page_title_font,
        )
        style.configure(
            "PageSubtitle.TLabel",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=small_font,
        )
        style.configure(
            "Header.TLabel",
            background=MAIN_HEADER,
        )
        welcome_background = "#081A33"
        welcome_foreground = "#DCEBFF"
        style.configure("WelcomeSplash.TFrame", background=welcome_background)
        style.configure(
            "WelcomeImage.TLabel",
            background=welcome_background,
        )
        style.configure(
            "WelcomeMascotBubble.TLabel",
            background="#DCEBFF",
            foreground="#081A33",
            font=(display_family, 7, "bold"),
            padding=(6, 3),
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "WelcomeEyebrow.TLabel",
            background=welcome_background,
            foreground="#8FB8FF",
            font=(display_family, 9),
        )
        style.configure(
            "WelcomeTitle.TLabel",
            background=welcome_background,
            foreground=welcome_foreground,
            font=(display_family, 13, "bold"),
        )
        for name, foreground in (
            ("WelcomeTitleShimmer1.TLabel", "#8FB8FF"),
            ("WelcomeTitleShimmer2.TLabel", "#F4C95D"),
            ("WelcomeTitleShimmer3.TLabel", "#7DD3FC"),
            ("WelcomeTitleShimmer4.TLabel", "#F4C95D"),
            ("WelcomeTitleShimmer5.TLabel", welcome_foreground),
        ):
            style.configure(
                name,
                background=welcome_background,
                foreground=foreground,
                font=(display_family, 13, "bold"),
            )
        style.configure(
            "WelcomeByline.TLabel",
            background=welcome_background,
            foreground="#9CC3FF",
            font=(display_family, 9),
        )
        style.configure(
            "WelcomeStatus.TLabel",
            background=welcome_background,
            foreground="#E5EEF9",
            font=default_font,
        )
        style.configure(
            "WelcomeStart.TButton",
            background=welcome_background,
            borderwidth=0,
            padding=0,
            relief="flat",
            focusthickness=1,
            focuscolor="#F4C95D",
        )
        style.map(
            "WelcomeStart.TButton",
            background=[
                ("active", welcome_background),
                ("pressed", welcome_background),
                ("disabled", welcome_background),
            ],
        )
        for name, border in (
            ("WelcomeStartGlow1.TFrame", "#F4C95D"),
            ("WelcomeStartGlow2.TFrame", "#3B82F6"),
            ("WelcomeStartGlow3.TFrame", "#7DD3FC"),
            ("WelcomeStartGlow4.TFrame", "#3B82F6"),
        ):
            style.configure(name, background=border)
        style.configure(
            "HeaderStatus.TLabel",
            background=FOREST_GREEN,
            foreground=IVORY_WHITE,
            font=button_font,
            bordercolor=OLD_GOLD,
            relief="solid",
            borderwidth=2,
            padding=(12, 5),
        )
        style.configure(
            "SectionHeader.TLabel",
            background=MAIN_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=section_title_font,
        )
        style.configure(
            "CardTitle.TLabel",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=card_title_font,
            padding=(8, 4),
        )
        style.configure(
            "CardValue.TLabel",
            background=CARD_BACKGROUND,
            foreground=MAIN_HEADER,
            font=card_value_font,
        )
        style.configure(
            "DashboardValue.TLabel",
            background=CARD_BACKGROUND,
            foreground=SKY_BLUE,
            font=card_value_font,
        )
        for name, foreground in (
            ("DashboardValueBlink1.TLabel", "#5BA4E5"),
            ("DashboardValueBlink2.TLabel", "#BDE4FF"),
            ("DashboardValueBlink3.TLabel", "#F7F1DD"),
            ("DashboardValueBlink4.TLabel", "#BDE4FF"),
            ("DashboardValueBlink5.TLabel", "#5BA4E5"),
        ):
            style.configure(
                name,
                background=CARD_BACKGROUND,
                foreground=foreground,
                font=card_value_font,
            )
        style.configure("ChoiceGroup.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "ChoiceSegment.TLabel",
            background=WHITE,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
            font=button_font,
            padding=(10, 5),
        )
        style.configure(
            "ChoiceSegmentSelected.TLabel",
            background=TEAL,
            foreground=WHITE,
            bordercolor=OLD_GOLD,
            relief="solid",
            borderwidth=2,
            font=button_font,
            padding=(10, 5),
        )
        style.configure(
            "OptionChip.TLabel",
            background=WHITE,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
            font=button_font,
            padding=(9, 5),
        )
        style.configure(
            "OptionChipSelected.TLabel",
            background=TEAL,
            foreground=IVORY_WHITE,
            bordercolor=OLD_GOLD,
            relief="solid",
            borderwidth=2,
            font=button_font,
            padding=(9, 5),
        )
        style.configure(
            "CardText.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
        )
        style.configure(
            "ResultSummary.TLabel",
            background=CARD_BACKGROUND,
            foreground=LOG_BACKGROUND,
        )
        style.configure(
            "CardBody.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=card_body_font,
        )
        style.configure(
            "CardStatus.TLabel",
            background=CARD_BACKGROUND,
            foreground=MAIN_HEADER,
            font=button_font,
        )
        style.configure(
            "ModuleDetail.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=button_font,
        )
        style.configure(
            "ModuleSuccess.TLabel",
            background=CARD_BACKGROUND,
            foreground=SUCCESS,
            font=button_font,
        )
        style.configure(
            "ModuleWarning.TLabel",
            background=CARD_BACKGROUND,
            foreground=WARNING,
            font=button_font,
        )
        style.configure(
            "ModuleError.TLabel",
            background=CARD_BACKGROUND,
            foreground=ERROR,
            font=button_font,
        )
        style.configure(
            "ModuleRunning.TLabel",
            background=CARD_BACKGROUND,
            foreground=SKY_BLUE,
            font=button_font,
        )
        style.configure(
            "ModuleNeutral.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=button_font,
        )
        style.configure(
            "EmptyState.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
        )
        style.configure(
            "StatusBar.TLabel",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=small_font,
        )
        style.configure(
            "Primary.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(11, 7),
            font=button_font,
            borderwidth=2,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#A5B79A"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "Secondary.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(10, 7),
            font=button_font,
            bordercolor=BORDER,
            borderwidth=2,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "PrimaryAction.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(11, 7),
            font=button_font,
            bordercolor=MAIN_HEADER,
            borderwidth=2,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "PrimaryAction.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#A5B79A"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "SecondaryAction.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            bordercolor=BORDER,
            padding=(10, 7),
            font=button_font,
            borderwidth=2,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "SecondaryAction.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "DangerAction.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(10, 7),
            font=button_font,
            bordercolor=MAIN_HEADER,
            borderwidth=2,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "DangerAction.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#BCA2A2"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        for alias, base_style in (
            ("RetroPrimary.TButton", "PrimaryAction.TButton"),
            ("RetroSecondary.TButton", "SecondaryAction.TButton"),
            ("RetroDanger.TButton", "DangerAction.TButton"),
            ("RetroTertiary.TButton", "Secondary.TButton"),
        ):
            style.configure(alias, **style.configure(base_style))
            style.map(alias, **style.map(base_style))
        style.configure(
            "Modern.TEntry",
            fieldbackground=IVORY_WHITE,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            insertcolor=TEXT_PRIMARY,
            padding=(7, 5),
        )
        style.configure(
            "Readonly.TEntry",
            fieldbackground="#E7DFC9",
            foreground=TEXT_SECONDARY,
            bordercolor=BORDER,
            padding=(7, 5),
        )
        style.configure(
            "LimitReadonly.TEntry",
            fieldbackground="#F4E9D3",
            foreground="#8B4A2F",
            bordercolor="#8B4A2F",
            insertcolor="#8B4A2F",
            padding=(7, 5),
        )
        style.configure(
            "CompactPanel.TFrame",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=2,
        )
        style.configure("CompactBody.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "CompactTitle.TLabel",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=(ui_family, 10, "bold"),
            padding=(8, 4),
        )
        style.configure(
            "CompactText.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=(ui_family, 8),
        )
        style.configure(
            "CompactStatus.TLabel",
            background=CARD_BACKGROUND,
            foreground=MAIN_HEADER,
            font=button_font,
        )
        style.configure(
            "Compact.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(8, 5),
            borderwidth=2,
            bordercolor=BORDER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=(ui_family, 8),
        )
        style.map(
            "Compact.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "CompactSoft.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(10, 5),
            borderwidth=2,
            bordercolor=BORDER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "CompactSoft.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#E7DFC9"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "Attendance.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(10, 5),
            borderwidth=2,
            bordercolor=BORDER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "Attendance.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "AttendancePrimary.TButton",
            background=FOREST_GREEN,
            foreground=IVORY_WHITE,
            padding=(11, 6),
            borderwidth=2,
            bordercolor=OLD_GOLD,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "AttendancePrimary.TButton",
            background=[
                ("pressed", "#477D31"),
                ("active", "#6DAF45"),
                ("focus", "#6DAF45"),
                ("disabled", "#A5B79A"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "AttendanceStartImage.TButton",
            background=CARD_BACKGROUND,
            foreground=WHITE,
            padding=(0, 0),
            borderwidth=0,
            focusthickness=0,
            focuscolor=CARD_BACKGROUND,
            font=button_font,
        )
        style.map(
            "AttendanceStartImage.TButton",
            background=[
                ("pressed", CARD_BACKGROUND),
                ("active", CARD_BACKGROUND),
                ("disabled", CARD_BACKGROUND),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "AttendanceDanger.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(10, 5),
            borderwidth=2,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "AttendanceDanger.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "CompactPrimary.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(9, 5),
            borderwidth=2,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "CompactPrimary.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#A5B79A"),
            ],
        )
        style.configure(
            "CompactDanger.TButton",
            background=TEAL,
            foreground=IVORY_WHITE,
            padding=(8, 5),
            borderwidth=2,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "CompactDanger.TButton",
            background=[
                ("pressed", TEAL_PRESSED),
                ("active", TEAL_HOVER),
                ("focus", TEAL_HOVER),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "Teal.Horizontal.TProgressbar",
            background=ROYAL_BLUE,
            troughcolor=IVORY_WHITE,
            bordercolor=BORDER,
            lightcolor=ROYAL_BLUE,
            darkcolor=ROYAL_BLUE,
            relief="solid",
            borderwidth=1,
        )
        for name, background in (
            ("StatusReady", SUCCESS),
            ("StatusRunning", SKY_BLUE),
            ("StatusWarning", WARNING),
            ("StatusError", ERROR),
            ("StatusInfo", INFO),
        ):
            style.configure(
                f"{name}.TLabel",
                background=background,
                foreground=IVORY_WHITE if name != "StatusWarning" else TEXT_PRIMARY,
                font=button_font,
                padding=(8, 4),
                relief="solid",
                bordercolor=BORDER,
                borderwidth=1,
            )
        style.configure(
            "StepActive.TLabel",
            background=ROYAL_BLUE,
            foreground=IVORY_WHITE,
            font=button_font,
            padding=(9, 5),
        )
        style.configure(
            "StepCompleted.TLabel",
            background=SUCCESS,
            foreground=IVORY_WHITE,
            font=button_font,
            padding=(9, 5),
        )
        style.configure(
            "StepPending.TLabel",
            background="#E5EDF2",
            foreground=TEXT_SECONDARY,
            font=button_font,
            padding=(9, 5),
        )
        style.configure("TNotebook", background=MAIN_BACKGROUND, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(10, 6),
            font=button_font,
            foreground=TEXT_SECONDARY,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", MAIN_HEADER), ("active", "#F4E2B9")],
            foreground=[("selected", IVORY_WHITE), ("active", TEXT_PRIMARY)],
        )
        style.configure("Success.TLabel", foreground=SUCCESS)
        style.configure("Warning.TLabel", foreground=WARNING)
        style.configure("Error.TLabel", foreground=ERROR)
        style.configure(
            "HealthHealthy.TLabel",
            background=CARD_BACKGROUND,
            foreground=SKY_BLUE,
            font=section_title_font,
        )
        style.configure(
            "HealthWarning.TLabel",
            background=CARD_BACKGROUND,
            foreground=WARNING,
            font=section_title_font,
        )
        style.configure(
            "HealthError.TLabel",
            background=CARD_BACKGROUND,
            foreground=ERROR,
            font=section_title_font,
        )
        style.configure(
            "Treeview",
            background=IVORY_WHITE,
            fieldbackground=IVORY_WHITE,
            foreground=TEXT_PRIMARY,
            rowheight=28,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            borderwidth=1,
            font=default_font,
        )
        style.map(
            "Treeview",
            background=[("selected", ROYAL_BLUE)],
            foreground=[("selected", IVORY_WHITE)],
        )
        style.configure(
            "Treeview.Heading",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            bordercolor=OLD_GOLD,
            relief="solid",
            font=section_title_font,
            padding=(6, 5),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", ROYAL_BLUE)],
            foreground=[("active", IVORY_WHITE)],
        )
        style.configure(
            "Log.TLabel",
            background=LOG_BACKGROUND,
            foreground=LOG_TEXT,
            font=(font_result.mono_family, 12),
        )
        return style
