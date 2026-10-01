"""Headless acceptance tests for the Sprint U1 Unified UI shell."""

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
from types import ModuleType

from config.app_config import OUTLOOK_ICON, PROJECT_ROOT
from unified_ui.icon_manager import IconManager, REQUIRED_ICON_NAMES
from unified_ui.pages import PAGE_REGISTRY

EXPECTED_PAGE_KEYS = (
    "dashboard",
    "attendance",
    "outlook_revisi",
    "hris",
    "utilities",
    "history",
    "settings",
    "system_health",
)

FORBIDDEN_ENGINE_ROOTS = {
    "attendance",
    "hris",
    "outlook",
    "utilities",
}


def test_page_registry_matches_sidebar_blueprint() -> None:
    keys = tuple(page.key for page in PAGE_REGISTRY)
    titles = tuple(page.title for page in PAGE_REGISTRY)

    assert keys == EXPECTED_PAGE_KEYS
    assert len(keys) == len(set(keys))
    assert "Utilities" in titles
    assert "Comparison Result" not in titles


def test_required_icon_paths_resolve_and_exist() -> None:
    manager = IconManager()
    paths = manager.required_paths()

    assert tuple(paths) == REQUIRED_ICON_NAMES
    assert all(path.parent == PROJECT_ROOT / "assets" / "icons" for path in paths.values())
    assert all(path.is_file() for path in paths.values())


def test_outlook_icon_uses_revisi_asset() -> None:
    assert OUTLOOK_ICON == PROJECT_ROOT / "assets" / "icons" / "outlook_revisi.ico"


def test_all_unified_ui_modules_are_importable() -> None:
    package = importlib.import_module("unified_ui")
    module_names = [
        module.name
        for module in pkgutil.walk_packages(
            package.__path__,
            prefix="unified_ui.",
        )
    ]

    assert module_names
    for module_name in module_names:
        importlib.import_module(module_name)


def test_unified_ui_source_has_no_engine_imports() -> None:
    source_root = PROJECT_ROOT / "unified_ui"

    for source_file in source_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.partition(".")[0]
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.partition(".")[0])

        assert imported_roots.isdisjoint(FORBIDDEN_ENGINE_ROOTS), source_file


def test_app_import_does_not_load_engines_or_create_database() -> None:
    databases_before = {
        path.resolve() for path in PROJECT_ROOT.rglob("OAS-K.db")
    }
    check_script = """
import sys
import ui.app
import main

forbidden = {"attendance", "hris", "outlook", "utilities"}
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise SystemExit(f"loaded={loaded}")
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", check_script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    databases_after = {
        path.resolve() for path in PROJECT_ROOT.rglob("OAS-K.db")
    }
    assert databases_after == databases_before


def test_main_entrypoint_routes_to_unified_ui(monkeypatch) -> None:
    import main

    calls: list[str] = []
    fake_app = ModuleType("ui.app")

    class FakeApp:
        def run(self) -> None:
            calls.append("ui.app")

    fake_app.create_app = FakeApp
    monkeypatch.setitem(sys.modules, "ui.app", fake_app)

    main.main()

    assert calls == ["ui.app"]
    assert callable(main.legacy_main)
