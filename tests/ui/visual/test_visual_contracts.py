from __future__ import annotations

import ast
from pathlib import Path

from PIL import Image

from config.app_config import PROJECT_ROOT
from ui import constants
from ui.icon_manager import IconManager


REQUIRED = {
    "dashboard",
    "attendance",
    "outlook_revisi",
    "hris",
    "utilities",
    "history",
    "settings",
    "system_health",
    "info",
    "success",
    "warning",
    "error",
    "refresh",
    "open_folder",
    "backup",
    "restore",
    "database",
}


def test_all_required_png_companions_are_rgba_22px() -> None:
    root = PROJECT_ROOT / "assets" / "icons" / "png"
    assert REQUIRED <= {path.stem for path in root.glob("*.png")}
    for name in REQUIRED:
        with Image.open(root / f"{name}.png") as image:
            assert image.size == (22, 22)
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[0] == 0


def test_icon_manager_prefers_png_and_missing_is_safe(tmp_path: Path) -> None:
    manager = IconManager(tmp_path)
    assert (
        manager.widget_icon_path("dashboard.ico") == tmp_path / "png" / "dashboard.png"
    )
    assert manager.load("missing.ico") is None


def test_corrupted_png_falls_back_without_crashing(tmp_path: Path) -> None:
    png = tmp_path / "png" / "broken.png"
    png.parent.mkdir()
    png.write_text("not an image", encoding="utf-8")
    assert IconManager(tmp_path).load("broken.ico") is None


def test_spacing_and_font_hierarchy_are_centralized() -> None:
    assert (
        constants.SPACE_XS,
        constants.SPACE_SM,
        constants.SPACE_MD,
        constants.SPACE_LG,
        constants.SPACE_XL,
    ) == (4, 8, 12, 16, 24)
    assert constants.PAGE_TITLE_FONT[1] > constants.DEFAULT_FONT[1]
    assert constants.CARD_VALUE_FONT[1] > constants.CARD_TITLE_FONT[1]


def test_ui8_visual_palette_is_centralized() -> None:
    expected = {
        "OUTLINE": "#222034",
        "ROYAL_BLUE": "#4D72B8",
        "SKY_BLUE": "#3A86C8",
        "SKY_BLUE_SOFT": "#E3F2FF",
        "SKY_BLUE_BORDER": "#4D72B8",
        "FOREST_GREEN": "#5E9C3A",
        "OLD_GOLD": "#D2A15A",
        "IVORY_WHITE": "#F7F1DD",
        "SOFT_BACKGROUND": "#EAE7DA",
        "BACKGROUND": "#EAE7DA",
        "CONTENT_BACKGROUND": "#EAE7DA",
        "CARD_BACKGROUND": "#F7F1DD",
        "TEXT_PRIMARY": "#222034",
        "BORDER": "#222034",
        "LOG_BACKGROUND": "#222034",
        "LOG_TEXT": "#F7F1DD",
    }
    assert {name: getattr(constants, name) for name in expected} == expected
    assert constants.SIDEBAR_WIDTH == 170


def test_ui5b_styles_cover_actions_inputs_log_status_and_steps() -> None:
    source = (PROJECT_ROOT / "ui" / "style_manager.py").read_text(encoding="utf-8")
    for style in (
        "ModernCard.TFrame",
        "RPGShadow.TFrame",
        "RPGAccent.TFrame",
        "CardTitle.TLabel",
        "DashboardValue.TLabel",
        "ChoiceSegmentSelected.TLabel",
        "OptionChipSelected.TLabel",
        "CompactSoft.TButton",
        "Attendance.TButton",
        "AttendancePrimary.TButton",
        "AttendanceDanger.TButton",
        "CardBody.TLabel",
        "PrimaryAction.TButton",
        "SecondaryAction.TButton",
        "DangerAction.TButton",
        "Modern.TEntry",
        "Readonly.TEntry",
        "LogPanel.TFrame",
        '"StatusReady"',
        '"StatusWarning"',
        '"StatusError"',
        "StepActive.TLabel",
        "StepCompleted.TLabel",
        "StepPending.TLabel",
        "Treeview.Heading",
    ):
        assert style in source
    assert "background=IVORY_WHITE" in source
    assert "background=ROYAL_BLUE" in source


def test_ui8_refinement_does_not_add_image_asset_pipeline_to_theme() -> None:
    checked = (
        PROJECT_ROOT / "ui" / "style_manager.py",
        PROJECT_ROOT / "ui" / "theme" / "palette.py",
        PROJECT_ROOT / "ui" / "widgets" / "content_card.py",
        PROJECT_ROOT / "ui" / "widgets" / "modern_card.py",
        PROJECT_ROOT / "ui" / "widgets" / "metric_card.py",
        PROJECT_ROOT / "ui" / "widgets" / "result_summary.py",
    )
    forbidden = ("PhotoImage", "ImageTk", "assets/icons", ".png", ".ico")
    for path in checked:
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)


def test_dashboard_metric_values_use_sky_blue_style() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "dashboard_page.py").read_text(
        encoding="utf-8"
    )
    assert 'value_style="DashboardValue.TLabel"' in source


def test_attendance_uses_polished_choice_chips_for_primary_controls() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "attendance_page.py").read_text(
        encoding="utf-8"
    )
    assert "SegmentedChoice" in source
    assert "OptionChip" in source
    assert "Attendance.TButton" in source
    assert "AttendancePrimary.TButton" in source


def test_ui5b_pages_and_ui7b1_pilot_use_approved_visual_foundations() -> None:
    attendance = (PROJECT_ROOT / "ui" / "pages" / "attendance_page.py").read_text(
        encoding="utf-8"
    )
    outlook = (
        PROJECT_ROOT / "ui" / "pages" / "outlook_revisi_page.py"
    ).read_text(encoding="utf-8")
    settings = (
        PROJECT_ROOT / "ui" / "pages" / "settings" / "module_configuration_section.py"
    ).read_text(encoding="utf-8")
    import_export = (
        PROJECT_ROOT / "ui" / "pages" / "settings" / "configuration_section.py"
    ).read_text(encoding="utf-8")
    grid = (PROJECT_ROOT / "ui" / "widgets" / "responsive_card_grid.py").read_text(
        encoding="utf-8"
    )

    assert "CompactPanel.TFrame" in attendance
    assert "CompactProgress" in attendance
    assert "ResponsiveCardGrid" not in attendance
    assert "ResponsiveCardGrid" not in outlook and "ModernCard" not in outlook
    assert "CompactPanel.TFrame" in outlook and "CompactProgress" in outlook
    assert "COMPACT_LOG_BACKGROUND" in attendance
    assert "LOG_BACKGROUND" in outlook
    assert "ModernCard" in settings
    assert "ModernCard" in import_export and "StepIndicator" in import_export
    assert "ttk.Scrollbar" in grid
    assert "event.width < self.breakpoint" in grid
    assert "columnspan=2" in grid


def test_visual_widgets_remain_presentation_only_and_lightweight() -> None:
    widget_names = ("modern_card.py", "responsive_card_grid.py", "step_indicator.py")
    forbidden_roots = {
        "attendance",
        "outlook",
        "outlook_revisi",
        "hris",
        "utilities",
        "shared",
        "sqlite3",
    }
    for name in widget_names:
        path = PROJECT_ROOT / "ui" / "widgets" / name
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots = {
            node.module.partition(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imported_roots.update(
            alias.name.partition(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert imported_roots.isdisjoint(forbidden_roots)
        assert "gradient" not in source.lower()
        assert "blur" not in source.lower()


def test_dpi_helper_is_guarded_and_not_called_at_import() -> None:
    path = PROJECT_ROOT / "ui" / "dpi.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    module_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    assert module_calls == []
    source = path.read_text(encoding="utf-8")
    assert 'sys.platform != "win32"' in source


def test_operational_pages_do_not_import_engines_or_configuration_reader() -> None:
    forbidden = {"attendance", "outlook", "outlook_revisi", "hris", "utilities"}
    for name in ("dashboard_page.py", "history_page.py", "system_health_page.py"):
        tree = ast.parse(
            (PROJECT_ROOT / "ui" / "pages" / name).read_text(encoding="utf-8")
        )
        roots = {
            node.module.partition(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert roots.isdisjoint(forbidden)
        assert "ConfigurationReader" not in (
            PROJECT_ROOT / "ui" / "pages" / name
        ).read_text(encoding="utf-8")
