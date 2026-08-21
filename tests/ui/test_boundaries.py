"""No-engine, no-persistence, and placeholder boundary tests."""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

from config.app_config import PROJECT_ROOT
from ui.page_registry import build_default_page_registry

FORBIDDEN_IMPORT_ROOTS = {
    "attendance",
    "outlook",
    "outlook_revisi",
    "hris",
    "utilities",
}


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


def test_ui_source_has_no_engine_imports() -> None:
    for path in (PROJECT_ROOT / "ui").rglob("*.py"):
        forbidden = set(FORBIDDEN_IMPORT_ROOTS)
        if path == PROJECT_ROOT / "ui" / "adapters" / "attendance_adapter.py":
            forbidden.remove("attendance")
        if path == PROJECT_ROOT / "ui" / "adapters" / "outlook_revisi_adapter.py":
            forbidden.remove("outlook")
        if path == PROJECT_ROOT / "ui" / "adapters" / "hris_adapter.py":
            forbidden.remove("hris")
        if path in {
            PROJECT_ROOT / "ui" / "adapters" / "comparison_result_adapter.py",
            PROJECT_ROOT / "ui" / "adapters" / "attachment_consolidation_adapter.py",
            PROJECT_ROOT / "ui" / "adapters" / "att_data_repair_adapter.py",
            PROJECT_ROOT / "ui" / "services" / "att_data_repair_service.py",
        }:
            forbidden.remove("utilities")
        assert _import_roots(path).isdisjoint(forbidden), path


def test_import_ui_does_not_load_engines_or_create_database(
    tmp_path: Path,
) -> None:
    script = """
import sys
import winreg
from pathlib import Path
writes = []
winreg.CreateKeyEx = lambda *a, **k: writes.append(('create', a)) or None
winreg.SetValueEx = lambda *a, **k: writes.append(('set', a))
winreg.DeleteKey = lambda *a, **k: writes.append(('delete', a))
import ui
forbidden = ('attendance.engine', 'outlook', 'outlook_revisi', 'hris', 'utilities')
assert not any(n == f or n.startswith(f + '.') for n in sys.modules for f in forbidden)
assert not list(Path('.').rglob('*.db'))
assert not writes
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ui_source_has_no_registry_or_database_services() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in (
            PROJECT_ROOT / "ui" / "pages",
            PROJECT_ROOT / "ui" / "widgets",
        )
        for path in root.rglob("*.py")
    )
    assert "winreg" not in source
    assert "StorageRegistryService" not in source
    assert "SchemaManager" not in source
    assert "SQLiteConnectionFactory" not in source


def test_no_json_state_pointer_contract() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "ui").rglob("*.py")
    )
    assert "storage_pointer.json" not in source
    assert "window_state.json" not in source


def test_all_ui_modules_are_importable() -> None:
    package = importlib.import_module("ui")
    modules = [
        item.name
        for item in pkgutil.walk_packages(package.__path__, prefix="ui.")
    ]
    assert modules
    for module_name in modules:
        importlib.import_module(module_name)


def test_placeholder_page_modules_are_registered() -> None:
    for definition in build_default_page_registry():
        module_name = f"ui.pages.{definition.page_id}_page"
        if definition.page_id == "outlook_revisi":
            module_name = "ui.pages.outlook_revisi_page"
        assert importlib.util.find_spec(module_name) is not None


def test_settings_page_does_not_run_recovery() -> None:
    path = PROJECT_ROOT / "ui" / "pages" / "settings_page.py"
    roots = _import_roots(path)
    assert "shared" not in roots


def test_history_page_does_not_query_database() -> None:
    source = (
        PROJECT_ROOT / "ui" / "pages" / "history_page.py"
    ).read_text(encoding="utf-8")
    assert "sqlite3" not in _import_roots(
        PROJECT_ROOT / "ui" / "pages" / "history_page.py"
    )
    assert "select " not in source.lower()


def test_system_health_does_not_run_checks() -> None:
    source = (
        PROJECT_ROOT / "ui" / "pages" / "system_health_page.py"
    ).read_text(encoding="utf-8")
    assert "DatabaseValidator" not in source
    assert "validate_data_root" not in source


def test_ui_does_not_import_configuration_reader() -> None:
    for path in (PROJECT_ROOT / "ui").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if path == PROJECT_ROOT / "ui" / "adapters" / "attendance_adapter.py":
            assert "AttendanceConfigurationReader" in source
            continue
        if path == PROJECT_ROOT / "ui" / "adapters" / "outlook_revisi_adapter.py":
            assert "OutlookRevisiConfigurationReader" in source
            continue
        if path == PROJECT_ROOT / "ui" / "adapters" / "hris_adapter.py":
            assert "HRISConfigurationReader" in source
            continue
        assert "config_manager" not in source
        assert "ConfigurationReader" not in source


def test_ui_does_not_import_legacy_main() -> None:
    for path in (PROJECT_ROOT / "ui").rglob("*.py"):
        assert "main" not in _import_roots(path)


def test_manual_entrypoint_has_main_guard() -> None:
    source = (
        PROJECT_ROOT / "tools" / "ui_test" / "run_unified_ui.py"
    ).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
