"""Shared default-theme contracts for the ATT & OT page."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from tkinter import ttk

import ui.theme.font_loader as font_loader_module
from ui.context import AppContext
from ui.pages.attendance_ot_page import AttendanceOTPage
from ui.theme.attendance_ot import (
    AttendanceOTPalette,
    resolve_attendance_ot_theme,
)


class _Analytics:
    def resolve_status(self):
        return SimpleNamespace(database_exists=False, database_valid=False)


def _page(tk_root, assets_path: Path) -> AttendanceOTPage:
    context = AppContext(
        project_root=assets_path.parent,
        assets_path=assets_path,
        application_version="test",
        logger=logging.getLogger("attendance-ot-theme-test"),
        app_services=SimpleNamespace(attendance_ot_service=_Analytics()),
    )
    return AttendanceOTPage(tk_root, context)


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def test_attendance_theme_uses_shared_application_fonts(tk_root) -> None:
    assets = Path(__file__).resolve().parents[3] / "assets"
    theme = resolve_attendance_ot_theme(tk_root, assets)

    assert theme.typography.heading_family in {"Silkscreen", "Segoe UI"}
    assert theme.typography.display_family == theme.typography.ui_family
    assert theme.typography.ui_family == "Segoe UI"
    assert theme.typography.mono_family in {"VT323", "Consolas", "TkFixedFont"}


def test_private_font_loading_is_idempotent(tmp_path, monkeypatch) -> None:
    font_path = (tmp_path / "Academic.ttf").resolve()
    font_path.write_bytes(b"font-placeholder")
    calls = []
    font_loader_module._LOADED_PRIVATE_FONT_PATHS.discard(font_path)
    monkeypatch.setattr(font_loader_module.sys, "platform", "win32")
    monkeypatch.setattr(
        font_loader_module,
        "_add_private_windows_font",
        lambda path: calls.append(path) or True,
    )

    first = font_loader_module.load_private_font_files((font_path,))
    second = font_loader_module.load_private_font_files((font_path,))

    assert first == ((font_path,), (), ())
    assert second == ((font_path,), (), ())
    assert calls == [font_path]
    font_loader_module._LOADED_PRIVATE_FONT_PATHS.discard(font_path)


def test_tabs_use_the_standard_native_notebook(tk_root) -> None:
    assets = Path(__file__).resolve().parents[3] / "assets"
    page = _page(tk_root, assets)

    assert isinstance(page.notebook, ttk.Notebook)
    assert tuple(
        page.notebook.tab(tab_id, "text") for tab_id in page.notebook.tabs()
    ) == page.TAB_TITLES
    assert not hasattr(page, "_tab_images")
    assert all(not page.notebook.tab(tab_id, "image") for tab_id in page.notebook.tabs())
    assert page.notebook.bind("<<NotebookTabChanged>>")


def test_attendance_page_uses_solid_surface_without_background_image(tk_root) -> None:
    assets = Path(__file__).resolve().parents[3] / "assets"
    page = _page(tk_root, assets)

    assert not hasattr(page, "chalkboard_backdrop")
    assert page.cget("style") == "AttendanceOTPage.TFrame"
    assert (
        page.dashboard_scroll.canvas.cget("background")
        == page.visual_theme.palette.surface
    )


def test_panel_borders_are_disabled_canvas_decoration(tk_root) -> None:
    assets = Path(__file__).resolve().parents[3] / "assets"
    page = _page(tk_root, assets)
    page.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    panels = (
        *page.kpi_cards.values(),
        page.attendance_trend_panel,
        page.trend_panel,
        page.top_department_panel,
        page.top_branch_panel,
    )
    for panel in panels:
        canvas = panel.border_canvas
        assert canvas.bind("<Button-1>") == ""
        for item in canvas.find_withtag("panel-border"):
            assert canvas.itemcget(item, "state") == "disabled"


def test_attendance_styles_do_not_mutate_global_button_style(tk_root) -> None:
    style = ttk.Style(tk_root)
    watched = ("background", "foreground", "font", "bordercolor")
    before = {option: style.lookup("TButton", option) for option in watched}
    assets = Path(__file__).resolve().parents[3] / "assets"

    page = _page(tk_root, assets)

    assert {option: style.lookup("TButton", option) for option in watched} == before
    assert page.apply_button.cget("style") == "AttendanceOTApply.TButton"
    assert page.reset_button.cget("style") == "AttendanceOTReset.TButton"
    for style_name in ("AttendanceOTApply.TButton", "AttendanceOTReset.TButton"):
        font = tk_root.tk.splitlist(style.lookup(style_name, "font"))
        assert font[0] == page.visual_theme.typography.heading_family
