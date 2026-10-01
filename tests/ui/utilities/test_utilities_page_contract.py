from __future__ import annotations

import ast
import logging
from types import SimpleNamespace

from config.app_config import PROJECT_ROOT
from ui.context import AppContext
from ui.pages.utilities_page import UtilitiesPage
from ui.utilities_models import ComparisonRunResult, UtilitiesFeature


def test_utilities_page_has_three_active_landing_features_and_no_engine_imports() -> (
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
    assert "Att Data Repair" in source


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
        "Buka Report",
        "Buka Log",
        "Retry",
        "Advanced / Per-run Override",
        "Gunakan output dari Settings",
            "Gunakan periode dari Settings",
            "Generate TXT",
            "Generate Excel Report",
            "Source Folder / Report",
        ):
            assert phrase in source
    assert "select_folder" in source
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


def test_utilities_success_shows_completion_popup(tk_root, tmp_path) -> None:
    completions = []
    services = SimpleNamespace(
        utilities_service=SimpleNamespace(landing_summaries=lambda: ()),
        task_runner=SimpleNamespace(),
        dialog_service=SimpleNamespace(
            completion=lambda *args: completions.append(args)
        ),
        file_system_service=SimpleNamespace(open_folder=lambda path: False),
    )
    context = AppContext(
        project_root=tmp_path,
        assets_path=PROJECT_ROOT / "assets",
        application_version="test",
        logger=logging.getLogger("ui7-utilities-completion"),
        app_services=services,
    )
    page = UtilitiesPage(tk_root, context)
    page._feature = UtilitiesFeature.COMPARISON_RESULT

    page._run_done(
        SimpleNamespace(
            success=True,
            value=ComparisonRunResult(
                True,
                False,
                "UI-UTIL-SUCCESS",
                "2026-07-01T00:00:00+00:00",
                "2026-07-01T00:00:01+00:00",
                tmp_path / "output",
                (),
            ),
        )
    )

    assert completions and completions[0][0] == "Comparison Result"


def test_att_data_repair_browse_uses_folder_picker(tk_root, tmp_path) -> None:
    selected = tmp_path / "reports"
    calls = []

    class Dialogs:
        def select_file(self, **kwargs):
            raise AssertionError("File picker must not be used for source folder")

        def select_folder(self, **kwargs):
            calls.append(kwargs)
            return selected

    services = SimpleNamespace(
        utilities_service=SimpleNamespace(landing_summaries=lambda: ()),
        task_runner=SimpleNamespace(),
        dialog_service=Dialogs(),
        file_system_service=SimpleNamespace(open_folder=lambda path: False),
    )
    context = AppContext(
        project_root=tmp_path,
        assets_path=PROJECT_ROOT / "assets",
        application_version="test",
        logger=logging.getLogger("ui7-utilities-att-data-repair-picker"),
        app_services=services,
    )
    page = UtilitiesPage(tk_root, context)
    page._feature = UtilitiesFeature.ATT_DATA_REPAIR

    page._browse_source(page.source_a_var)

    assert page.source_a_var.get() == str(selected)
    assert calls == [
        {
            "title": "Pilih Folder Source Report",
        }
    ]
