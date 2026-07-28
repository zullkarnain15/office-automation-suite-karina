from __future__ import annotations

import ast

from config.app_config import PROJECT_ROOT


def test_utilities_page_has_only_two_active_landing_features_and_no_engine_imports() -> (
    None
):
    path = PROJECT_ROOT / "ui" / "pages" / "utilities_page.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module.partition(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "utilities" not in imports
    assert "Merge TXT" not in source
    assert "Merge Excel" not in source
    assert "Comparison Result" in source
    assert "Attachment Consolidation" in source


def test_workspace_contract_includes_validation_cancel_recovery_and_advanced() -> None:
    source = (PROJECT_ROOT / "ui" / "pages" / "utilities_page.py").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "Konfigurasi:",
        "Periode & Workflow",
        "Process Log",
        "Periksa Data",
        "Batal",
        "Buka Output",
        "Retry",
        "Advanced / Per-run Override",
        "Gunakan output dari Settings",
        "Gunakan periode dari Settings",
    ):
        assert phrase in source
    assert "ResponsiveCardGrid" not in source
    assert "ModernCard" not in source
    assert "CompactPanel.TFrame" in source
