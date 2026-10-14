from __future__ import annotations

import ast
from pathlib import Path

from config.app_config import PROJECT_ROOT


def test_no_business_engine_imported_by_updater() -> None:
    forbidden = {"attendance", "outlook", "hris", "utilities", "ui", "shared"}
    for path in (PROJECT_ROOT / "updater").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.partition(".")[0])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.partition(".")[0] for alias in node.names)
        assert imported.isdisjoint(forbidden), path


def test_updater_does_not_request_administrator_access() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "updater").glob("*.py")
    ).casefold()
    forbidden = {"runas", "shell_execute", "requireadministrator", "administrator"}
    assert forbidden.isdisjoint(set(token for token in forbidden if token in combined))
