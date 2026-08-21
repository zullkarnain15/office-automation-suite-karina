"""Page registry, metadata, icon, context, and window contracts."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

import pytest

from config.app_config import APP_VERSION, PROJECT_ROOT
from ui.constants import (
    APP_TITLE,
    PAGE_ORDER,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
)
from ui.context import AppContext
from ui.icon_manager import IconManager
from ui.models import PageDefinition
from ui.page_registry import PageRegistry, build_default_page_registry
from ui.window_state import WindowState


def test_page_registry_has_exactly_eight_pages() -> None:
    assert len(build_default_page_registry()) == 8


def test_page_order_is_locked() -> None:
    assert build_default_page_registry().page_ids == PAGE_ORDER


def test_duplicate_page_id_is_rejected() -> None:
    item = PageDefinition("a", "A", "Subtitle", "a.ico", lambda *_: object())
    with pytest.raises(ValueError, match="Duplicate"):
        PageRegistry([item, item])


def test_page_metadata_is_complete() -> None:
    for definition in build_default_page_registry():
        assert definition.page_id
        assert definition.title
        assert definition.subtitle
        assert definition.icon_name.endswith(".ico")
        assert callable(definition.factory)


def test_utilities_remains_main_menu() -> None:
    definition = build_default_page_registry().get("utilities")
    assert definition.title == "Utilities"
    assert "Comparison Result" not in {
        item.title for item in build_default_page_registry()
    }


def test_all_menu_icons_exist_or_have_fallback() -> None:
    manager = IconManager(PROJECT_ROOT / "assets" / "icons")
    assert all(
        manager.exists(definition.icon_name)
        for definition in build_default_page_registry()
    )


def test_icon_manager_missing_icon_is_safe(tmp_path: Path) -> None:
    manager = IconManager(
        tmp_path,
        logger=logging.getLogger("icon-test"),
    )
    assert manager.load("missing.ico") is None
    assert manager.cached_icon_names == ("missing.ico",)


def test_icon_manager_corrupted_icon_is_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "broken.ico"
    path.write_bytes(b"not-an-icon")
    monkeypatch.setattr(
        tk,
        "PhotoImage",
        lambda **kwargs: (_ for _ in ()).throw(tk.TclError("corrupt")),
    )
    assert IconManager(tmp_path).load("broken.ico") is None


def test_icon_manager_resolve_blocks_parent_path(tmp_path: Path) -> None:
    manager = IconManager(tmp_path)
    assert manager.resolve("../outside.ico") == tmp_path / "outside.ico"


def test_app_context_has_no_engine_dependency(tmp_path: Path) -> None:
    context = AppContext(
        tmp_path,
        tmp_path / "assets",
        APP_VERSION,
        logging.getLogger("context-test"),
    )
    assert context.services == {}
    assert not hasattr(context, "engine")
    assert not hasattr(context, "attendance_engine")


def test_application_title_is_exact() -> None:
    assert APP_TITLE == "Office Automation Suite – Karina by. ZSH"


def test_default_and_minimum_window_sizes() -> None:
    assert (WINDOW_WIDTH, WINDOW_HEIGHT) == (1180, 720)
    assert (WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT) == (1000, 640)


def test_window_state_is_in_memory_model() -> None:
    state = WindowState()
    state.update_geometry(1200, 700, maximized=True)
    assert (state.width, state.height, state.maximized) == (1200, 700, True)


def test_page_definition_rejects_empty_metadata() -> None:
    with pytest.raises(ValueError, match="title"):
        PageDefinition("id", "", "subtitle", "icon.ico", lambda *_: object())
