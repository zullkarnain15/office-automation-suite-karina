"""Lightweight ttk theme definitions for the Unified UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BACKGROUND = "#F5F7FA"
SIDEBAR_BACKGROUND = "#FFFFFF"
HEADER_BACKGROUND = "#1F4E78"
ACCENT = "#2F80ED"
PRIMARY_ACTION = "#2E8B57"
TEXT_PRIMARY = "#1F2937"
TEXT_SECONDARY = "#6B7280"
BORDER = "#D9E2EC"
SELECTED_NAVIGATION = "#EAF3FF"
SUCCESS = "#2E8B57"
WARNING = "#F4A261"
ERROR = "#D64545"
WHITE = "#FFFFFF"

DEFAULT_FONT = ("Segoe UI", 10)
SMALL_FONT = ("Segoe UI", 9)
TITLE_FONT = ("Segoe UI", 22, "bold")
PAGE_TITLE_FONT = ("Segoe UI", 18, "bold")
SECTION_TITLE_FONT = ("Segoe UI", 12, "bold")
NAVIGATION_FONT = ("Segoe UI", 10)

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 600


def apply_theme(root: tk.Misc) -> ttk.Style:
    """Configure and return the shared ttk light theme."""

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", font=DEFAULT_FONT)
    style.configure("App.TFrame", background=BACKGROUND)
    style.configure("Sidebar.TFrame", background=SIDEBAR_BACKGROUND)
    style.configure("Header.TFrame", background=HEADER_BACKGROUND)
    style.configure("Card.TFrame", background=WHITE, relief="solid", borderwidth=1)
    style.configure("Status.TFrame", background=WHITE)

    style.configure(
        "HeaderTitle.TLabel",
        background=HEADER_BACKGROUND,
        foreground=WHITE,
        font=TITLE_FONT,
    )
    style.configure(
        "HeaderSubtitle.TLabel",
        background=HEADER_BACKGROUND,
        foreground="#DDEBFA",
        font=DEFAULT_FONT,
    )
    style.configure(
        "HeaderCompany.TLabel",
        background=HEADER_BACKGROUND,
        foreground=WHITE,
        font=SECTION_TITLE_FONT,
    )
    style.configure(
        "SidebarTitle.TLabel",
        background=SIDEBAR_BACKGROUND,
        foreground=TEXT_SECONDARY,
        font=("Segoe UI", 9, "bold"),
    )
    style.configure(
        "PageTitle.TLabel",
        background=BACKGROUND,
        foreground=TEXT_PRIMARY,
        font=PAGE_TITLE_FONT,
    )
    style.configure(
        "PageDescription.TLabel",
        background=BACKGROUND,
        foreground=TEXT_SECONDARY,
        font=DEFAULT_FONT,
    )
    style.configure(
        "CardTitle.TLabel",
        background=WHITE,
        foreground=TEXT_PRIMARY,
        font=SECTION_TITLE_FONT,
    )
    style.configure(
        "CardText.TLabel",
        background=WHITE,
        foreground=TEXT_SECONDARY,
        font=DEFAULT_FONT,
    )
    style.configure(
        "CardStatus.TLabel",
        background=WHITE,
        foreground=ACCENT,
        font=("Segoe UI", 9, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=WHITE,
        foreground=TEXT_SECONDARY,
        font=SMALL_FONT,
    )
    style.configure(
        "StatusStrong.TLabel",
        background=WHITE,
        foreground=TEXT_PRIMARY,
        font=("Segoe UI", 9, "bold"),
    )

    style.configure(
        "Navigation.TButton",
        background=SIDEBAR_BACKGROUND,
        foreground=TEXT_PRIMARY,
        borderwidth=0,
        focusthickness=0,
        focuscolor=SIDEBAR_BACKGROUND,
        anchor="w",
        padding=(14, 10),
        font=NAVIGATION_FONT,
    )
    style.map(
        "Navigation.TButton",
        background=[
            ("active", SELECTED_NAVIGATION),
            ("pressed", SELECTED_NAVIGATION),
        ],
        foreground=[("active", HEADER_BACKGROUND)],
    )
    style.configure(
        "Selected.Navigation.TButton",
        background=SELECTED_NAVIGATION,
        foreground=HEADER_BACKGROUND,
        borderwidth=0,
        focusthickness=0,
        focuscolor=SELECTED_NAVIGATION,
        anchor="w",
        padding=(14, 10),
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Selected.Navigation.TButton",
        background=[
            ("active", SELECTED_NAVIGATION),
            ("pressed", SELECTED_NAVIGATION),
        ],
    )

    return style
