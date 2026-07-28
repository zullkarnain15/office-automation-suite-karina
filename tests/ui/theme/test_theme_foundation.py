from __future__ import annotations

from pathlib import Path

from config.app_config import PROJECT_ROOT
from ui import constants
from ui.icon_manager import IconManager
from ui.theme.font_loader import load_theme_fonts
from ui.theme.palette import palette
from ui.theme.typography import typography


def test_ui8_palette_constants_are_centralized() -> None:
    assert constants.OUTLINE == "#33664d"
    assert constants.ROYAL_BLUE == "#4D72B8"
    assert constants.FOREST_GREEN == "#5E9C3A"
    assert constants.OLD_GOLD == "#D2A15A"
    assert constants.IVORY_WHITE == "#F7F1DD"
    assert constants.SOFT_BACKGROUND == "#EAE7DA"
    assert constants.ERROR == constants.DANGER_RED
    assert constants.ERROR not in {constants.OLD_GOLD, constants.FOREST_GREEN}
    assert constants.MAIN_BACKGROUND == palette.soft_background


def test_ui8_font_files_exist_and_sizes_are_compact() -> None:
    assert all(path.is_file() for path in typography.expected_files)
    assert constants.DEFAULT_FONT[1] == 9
    assert constants.SMALL_FONT[1] == 8
    assert constants.BUTTON_FONT[1] == 8
    assert 14 <= constants.PAGE_TITLE_FONT[1] <= 16
    assert 12 <= constants.LOG_FONT[1] <= 14


def test_font_loader_missing_fonts_fallback_without_registry_write(tmp_path: Path) -> None:
    class MissingSpec:
        expected_files = (tmp_path / "missing.ttf",)
        ui_family = "NoSuchUiFont"
        ui_fallback = "Segoe UI"
        display_family = "NoSuchDisplayFont"
        display_fallback = "Segoe UI"
        mono_family = "NoSuchMonoFont"
        mono_fallback = "Consolas"

    result = load_theme_fonts(spec=MissingSpec())  # type: ignore[arg-type]
    assert result.loaded == ()
    assert result.failed == ()
    assert result.missing == (tmp_path / "missing.ttf",)
    assert result.ui_family == "Segoe UI"
    assert result.display_family == "Segoe UI"
    assert result.mono_family == "Consolas"


def test_button_styles_define_required_retro_states() -> None:
    source = (PROJECT_ROOT / "ui" / "style_manager.py").read_text(encoding="utf-8")
    for style in (
        "RetroPrimary.TButton",
        "RetroSecondary.TButton",
        "RetroDanger.TButton",
        "RetroTertiary.TButton",
    ):
        assert style in source
    for state in ("pressed", "active", "focuscolor", "disabled"):
        assert state in source
    assert '"DangerAction.TButton"' in source
    assert "ERROR" in source


def test_icon_scaling_uses_nearest_neighbor_and_missing_is_safe(tmp_path: Path) -> None:
    source = (PROJECT_ROOT / "ui" / "icon_manager.py").read_text(encoding="utf-8")
    assert "Image.Resampling.NEAREST" in source
    manager = IconManager(tmp_path)
    assert manager.load("missing.ico", size=18) is None
