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
    MAIN_BACKGROUND,
    MAIN_HEADER,
    OLD_GOLD,
    OPTION_CHIP_SELECTED_BACKGROUND,
    OPTION_CHIP_SELECTED_BORDER,
    OPTION_CHIP_SELECTED_FOREGROUND,
    PAGE_TITLE_FONT,
    PRIMARY_ACTION,
    ROYAL_BLUE,
    SECTION_TITLE_FONT,
    SIDEBAR_ACTIVE,
    SIDEBAR_BACKGROUND,
    SIDEBAR_HOVER,
    SKY_BLUE,
    SMALL_FONT,
    SUCCESS,
    TEAL,
    TEAL_DARK,
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
        style.configure("OASK.TFrame", background=MAIN_BACKGROUND)
        style.configure("PageBackground.TFrame", background=BACKGROUND)
        style.configure("Sidebar.TFrame", background=SIDEBAR_BACKGROUND)
        style.configure("Header.TFrame", background=MAIN_HEADER)
        style.configure(
            "ContentCard.TFrame",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "ModernCard.TFrame",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure("CardAccent.TFrame", background=TEAL)
        style.configure("CardBody.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "SettingsPanel.TLabelframe",
            background=CARD_BACKGROUND,
            bordercolor=BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "SettingsPanel.TLabelframe.Label",
            background=MAIN_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=section_title_font,
        )
        style.configure(
            "SettingsPanel.TCheckbutton",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=default_font,
        )
        style.configure("LogPanel.TFrame", background=LOG_BACKGROUND)
        style.configure("StatusBar.TFrame", background=WHITE)

        style.configure(
            "SidebarBrand.TLabel",
            background=SIDEBAR_BACKGROUND,
            foreground=OLD_GOLD,
            font=(display_family, 12),
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
            padding=(9, 7),
            borderwidth=1,
            bordercolor=SIDEBAR_BACKGROUND,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=(ui_family, 10),
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
            padding=(9, 7),
            borderwidth=1,
            bordercolor=OLD_GOLD,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=(ui_family, 10, "bold"),
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
            foreground="#D9EAF7",
        )
        style.configure(
            "Header.TLabel",
            background=MAIN_HEADER,
        )
        style.configure(
            "WelcomeImage.TLabel",
            background=MAIN_BACKGROUND,
        )
        style.configure(
            "WelcomeEyebrow.TLabel",
            background=MAIN_BACKGROUND,
            foreground=OLD_GOLD,
            font=(display_family, 9),
        )
        style.configure(
            "WelcomeTitle.TLabel",
            background=MAIN_BACKGROUND,
            foreground=FOREST_GREEN,
            font=(display_family, 13),
        )
        style.configure(
            "WelcomeByline.TLabel",
            background=MAIN_BACKGROUND,
            foreground=ROYAL_BLUE,
            font=(display_family, 9),
        )
        style.configure(
            "WelcomeStatus.TLabel",
            background=MAIN_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=default_font,
        )
        style.configure(
            "WelcomeStart.TButton",
            background=MAIN_BACKGROUND,
            borderwidth=0,
            padding=0,
            relief="flat",
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "WelcomeStart.TButton",
            background=[
                ("active", MAIN_BACKGROUND),
                ("pressed", MAIN_BACKGROUND),
                ("disabled", MAIN_BACKGROUND),
            ],
        )
        style.configure(
            "HeaderStatus.TLabel",
            background=MAIN_HEADER,
            foreground=WHITE,
            font=button_font,
        )
        style.configure(
            "SectionHeader.TLabel",
            background=MAIN_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=section_title_font,
        )
        style.configure(
            "CardTitle.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=card_title_font,
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
            background=OLD_GOLD,
            foreground=WHITE,
            bordercolor=TEAL_DARK,
            relief="solid",
            borderwidth=1,
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
            background=OPTION_CHIP_SELECTED_BACKGROUND,
            foreground=OPTION_CHIP_SELECTED_FOREGROUND,
            bordercolor=OPTION_CHIP_SELECTED_BORDER,
            relief="solid",
            borderwidth=1,
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
            "EmptyState.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
        )
        style.configure(
            "StatusBar.TLabel",
            background=WHITE,
            foreground=TEXT_SECONDARY,
            font=small_font,
        )
        style.configure(
            "Primary.TButton",
            background=PRIMARY_ACTION,
            foreground=WHITE,
            padding=(10, 6),
            font=button_font,
            borderwidth=1,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("pressed", "#477D31"),
                ("active", FOREST_GREEN),
                ("disabled", "#A5B79A"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "Secondary.TButton",
            background=WHITE,
            foreground=MAIN_HEADER,
            padding=(9, 6),
            font=button_font,
            bordercolor=BORDER,
            borderwidth=1,
            focusthickness=1,
            focuscolor=ROYAL_BLUE,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("pressed", "#DDD5BF"),
                ("active", "#FFF8E8"),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "PrimaryAction.TButton",
            background=PRIMARY_ACTION,
            foreground=WHITE,
            padding=(10, 6),
            font=button_font,
            bordercolor=MAIN_HEADER,
            borderwidth=1,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "PrimaryAction.TButton",
            background=[
                ("pressed", "#477D31"),
                ("active", FOREST_GREEN),
                ("disabled", "#A5B79A"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "SecondaryAction.TButton",
            background=WHITE,
            foreground=MAIN_HEADER,
            bordercolor=BORDER,
            padding=(9, 6),
            font=button_font,
            borderwidth=1,
            focusthickness=1,
            focuscolor=ROYAL_BLUE,
        )
        style.map(
            "SecondaryAction.TButton",
            background=[
                ("pressed", "#DDD5BF"),
                ("active", "#FFF8E8"),
                ("disabled", "#D7D1C0"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "DangerAction.TButton",
            background=ERROR,
            foreground=WHITE,
            padding=(9, 6),
            font=button_font,
            bordercolor=MAIN_HEADER,
            borderwidth=1,
            focusthickness=1,
            focuscolor=OLD_GOLD,
        )
        style.map(
            "DangerAction.TButton",
            background=[
                ("pressed", "#922E2E"),
                ("active", ERROR),
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
            fieldbackground=WHITE,
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
            bordercolor="#DCE4EA",
            relief="solid",
            borderwidth=1,
        )
        style.configure("CompactBody.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "CompactTitle.TLabel",
            background=CARD_BACKGROUND,
            foreground="#243746",
            font=(ui_family, 10, "bold"),
        )
        style.configure(
            "CompactText.TLabel",
            background=CARD_BACKGROUND,
            foreground="#687887",
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
            padding=(8, 5),
            borderwidth=1,
            bordercolor=BORDER,
            focusthickness=1,
            focuscolor=ROYAL_BLUE,
            font=(ui_family, 8),
        )
        style.configure(
            "CompactSoft.TButton",
            background="#F3E1B9",
            foreground=MAIN_HEADER,
            padding=(10, 5),
            borderwidth=1,
            bordercolor=TEAL_DARK,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "CompactSoft.TButton",
            background=[
                ("pressed", "#E7C884"),
                ("active", "#F7E6BF"),
                ("disabled", "#E7DFC9"),
            ],
            foreground=[("disabled", "#77716A")],
        )
        style.configure(
            "Attendance.TButton",
            background="#8B4A2F",
            foreground=WHITE,
            padding=(10, 5),
            borderwidth=1,
            bordercolor="#5D2F1E",
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "Attendance.TButton",
            background=[
                ("pressed", "#6F3924"),
                ("active", "#A65A38"),
                ("disabled", "#A98B7D"),
            ],
            foreground=[("disabled", "#ECE5D0")],
        )
        style.configure(
            "AttendancePrimary.TButton",
            background=SIDEBAR_ACTIVE,
            foreground=WHITE,
            padding=(10, 5),
            borderwidth=1,
            bordercolor=OLD_GOLD,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "AttendancePrimary.TButton",
            background=[
                ("pressed", "#3F5E98"),
                ("active", SIDEBAR_ACTIVE),
                ("disabled", "#A5B6D7"),
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
            background="#B83A3A",
            foreground=WHITE,
            padding=(10, 5),
            borderwidth=1,
            bordercolor="#6F231F",
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.configure(
            "CompactPrimary.TButton",
            background=PRIMARY_ACTION,
            foreground=WHITE,
            padding=(9, 5),
            borderwidth=1,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.map(
            "CompactPrimary.TButton",
            background=[
                ("pressed", "#477D31"),
                ("active", FOREST_GREEN),
                ("disabled", "#A5B79A"),
            ],
        )
        style.configure(
            "CompactDanger.TButton",
            background=ERROR,
            foreground=WHITE,
            padding=(8, 5),
            borderwidth=1,
            bordercolor=MAIN_HEADER,
            focusthickness=1,
            focuscolor=OLD_GOLD,
            font=button_font,
        )
        style.configure(
            "Teal.Horizontal.TProgressbar",
            background=TEAL,
            troughcolor="#DCE6EC",
            bordercolor=BORDER,
            lightcolor=TEAL,
            darkcolor=TEAL_DARK,
        )
        for name, foreground in (
            ("StatusReady", SUCCESS),
            ("StatusWarning", WARNING),
            ("StatusError", ERROR),
            ("StatusInfo", INFO),
        ):
            style.configure(
                f"{name}.TLabel",
                background=CARD_BACKGROUND,
                foreground=foreground,
                font=button_font,
                padding=(6, 3),
            )
        style.configure(
            "StepActive.TLabel",
            background=TEAL,
            foreground=WHITE,
            font=button_font,
            padding=(9, 5),
        )
        style.configure(
            "StepCompleted.TLabel",
            background=SUCCESS,
            foreground=WHITE,
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
            background=[("selected", WHITE), ("active", "#EAF1F5")],
            foreground=[("selected", MAIN_HEADER)],
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
        style.configure("Treeview", rowheight=24, bordercolor=BORDER, font=default_font)
        style.configure("Treeview.Heading", font=section_title_font)
        return style
