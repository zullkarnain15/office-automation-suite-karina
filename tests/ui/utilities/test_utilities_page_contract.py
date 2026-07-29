from __future__ import annotations

import ast
import logging
from types import SimpleNamespace

from config.app_config import PROJECT_ROOT
from ui.context import AppContext
from ui.pages.utilities_page import UtilitiesPage
from ui.utilities_models import ComparisonRunResult


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


def test_utilities_validation_status_uses_visual_state_styles(
    tk_root, tmp_path
) -> None:
    services = SimpleNamespace(
        utilities_service=SimpleNamespace(landing_summaries=lambda: ()),
        task_runner=SimpleNamespace(),
        dialog_service=SimpleNamespace(),
        file_system_service=SimpleNamespace(open_folder=lambda path: False),
    )
    context = AppContext(
        project_root=tmp_path,
        assets_path=PROJECT_ROOT / "assets",
        application_version="test",
        logger=logging.getLogger("ui7-utilities-visual-status"),
        app_services=services,
    )
    page = UtilitiesPage(tk_root, context)

    page._set_validation_status("Siap")
    assert page.validation_status_label.cget("style") == "StatusReady.TLabel"

    page._set_validation_status("Sedang berjalan")
    assert page.validation_status_label.cget("style") == "StatusRunning.TLabel"

    page._set_validation_status("Perlu perhatian")
    assert page.validation_status_label.cget("style") == "StatusWarning.TLabel"

    page._run_done(
        SimpleNamespace(
            success=True,
            value=ComparisonRunResult(
                True,
                False,
                "UI-UTIL-WARN",
                "2026-07-01T00:00:00+00:00",
                "2026-07-01T00:00:01+00:00",
                tmp_path / "output",
                (),
                warning_count=1,
            ),
        )
    )
    assert page.validation_status_var.get() == "Berhasil dengan peringatan"
    assert page.validation_status_label.cget("style") == "StatusWarning.TLabel"
