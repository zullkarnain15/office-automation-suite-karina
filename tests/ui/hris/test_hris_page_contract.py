from __future__ import annotations

import ast
import logging

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.app import OASKUnifiedApp
from ui.context import AppContext
from ui.services.service_container import build_default_app_services


def test_page_has_no_engine_browser_database_registry_or_json_imports() -> None:
    path = PROJECT_ROOT / "ui" / "pages" / "hris_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"hris", "playwright", "sqlite3", "json", "shared"}
    roots = {
        node.module.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    roots.update(
        alias.name.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert roots.isdisjoint(forbidden)


def test_page_uses_compact_layout_and_assisted_recovery_controls() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "hris_page.py").read_text(
        encoding="utf-8"
    )
    assert "ResponsiveCardGrid" not in source
    assert "ModernCard" not in source
    assert "CompactPanel.TFrame" in source
    assert "CompactProgress" in source
    assert "Sudah Submitted" in source
    assert "Login Selesai" in source
    assert "Advanced / Manual Fallback" in source
    assert "Automation klik dipahami" in source
    assert "Login Mode" not in source
    assert "Manual Login" not in source
    assert "Auto Login" not in source
    assert "login_mode_var" not in source
    assert "DateEntry(" in source
    assert "start_entry.get_iso()" in source
    assert "end_entry.get_iso()" in source


def test_opening_hris_page_has_zero_side_effects(tk_root, tmp_path) -> None:
    data_root = tmp_path / "never-create" / "Data"
    backend = FakeRegistryBackend()
    services = build_default_app_services(
        tk_root,
        application_version=APP_VERSION,
        project_root=PROJECT_ROOT,
        registry=StorageRegistryService(backend),
        default_data_root=data_root,
    )
    context = AppContext(
        project_root=PROJECT_ROOT,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("ui6-zero-side-effect"),
        app_services=services,
    )
    app = OASKUnifiedApp(tk_root, context=context)
    assert app.navigate("hris")
    tk_root.update()
    assert backend.write_count == 0
    assert backend.delete_count == 0
    assert not data_root.exists()
    assert not list(tmp_path.rglob("*.db"))
    page = app.navigation._cache["hris"]
    assert page.fallback_var.get() is False
    assert page.can_navigate_away()
    assert app.close()
