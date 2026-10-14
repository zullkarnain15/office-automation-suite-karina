from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from config.app_config import APP_VERSION, PROJECT_ROOT
from ui.context import AppContext
from ui.pages.hris_page import HRISPage
from ui.services.hris_service import HRISService
from ui.services.task_runner import TaskResult


class DeferredRunner:
    def __init__(self):
        self.pending = []

    def submit(self, function, *, on_done, **kwargs):
        self.pending.append((function, on_done))

    def complete(self, index):
        function, callback = self.pending[index]
        try:
            result = TaskResult(str(index), True, value=function())
        except Exception as exc:
            result = TaskResult(str(index), False, error=str(exc))
        callback(result)


@pytest.fixture
def source_page(tk_root, tmp_path):
    runner = DeferredRunner()
    services = SimpleNamespace(
        hris_service=HRISService(None, None),
        task_runner=runner,
        dialog_service=Mock(),
        file_system_service=Mock(),
    )
    page = HRISPage(tk_root, AppContext(
        project_root=tmp_path,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("hris-source-tests"),
        app_services=services,
    ))
    for workflow, count in (("HO", 1), ("BRANCH", 2)):
        folder = tmp_path / workflow
        folder.mkdir()
        for index in range(count):
            (folder / f"{index}.txt").write_text("test", encoding="utf-8")
        page._configured_sources[workflow] = folder
    yield page, runner
    page.dispose()
    page.destroy()


def click_source(page, workflow):
    page.source_type_choice.buttons[workflow].event_generate("<Button-1>")


def test_click_updates_visible_path_and_ignores_late_scan(source_page):
    page, runner = source_page
    page._apply_source_mode()
    click_source(page, "BRANCH")
    assert page.source_entry.get() == str(page._configured_sources["BRANCH"])
    runner.complete(1)
    assert page.source_summary_var.get() == "TXT ditemukan/valid: 2"
    runner.complete(0)
    assert page.source_summary_var.get() == "TXT ditemukan/valid: 2"
    click_source(page, "HO")
    runner.complete(2)
    assert page.source_entry.get() == str(page._configured_sources["HO"])
    assert page.source_summary_var.get() == "TXT ditemukan/valid: 1"


def test_missing_configuration_invalidates_pending_scan(source_page):
    page, runner = source_page
    page._apply_source_mode()
    page._configured_sources["BRANCH"] = None
    click_source(page, "BRANCH")
    runner.complete(0)
    assert page.source_entry.get() == ""
    assert "Branch TXT Source Folder belum dikonfigurasi" in page.source_summary_var.get()


def test_repeated_scan_same_path_uses_latest_result(source_page):
    page, runner = source_page
    page._apply_source_mode()
    page.refresh_source()
    runner.complete(1)
    (page._configured_sources["HO"] / "late.txt").touch()
    runner.complete(0)
    assert page.source_summary_var.get() == "TXT ditemukan/valid: 1"


def test_manual_edit_and_disposal_ignore_pending_callbacks(source_page):
    page, runner = source_page
    page._apply_source_mode()
    page.use_configured_source_check.invoke()
    page.source_var.set("manual-folder")
    runner.complete(0)
    assert page.source_summary_var.get() == "TXT source: Belum diperiksa"
    page.refresh_source()
    page.dispose()
    runner.complete(1)
    assert page.source_summary_var.get() == "Membaca folder TXT..."


@pytest.mark.parametrize("configured", [True, False])
def test_busy_locks_source_and_restores_global_or_manual_mode(source_page, configured):
    page, runner = source_page
    page.use_configured_source_var.set(configured)
    page._apply_source_mode()
    if not configured:
        page.source_var.set("manual-folder")
    original = page.source_entry.get()
    page._set_busy(True)
    click_source(page, "BRANCH")
    page.use_configured_source_check.invoke()
    page.source_browse_button.invoke()
    assert page.workflow_var.get() == "HO"
    assert page.use_configured_source_var.get() is configured
    assert page.source_entry.instate(("disabled",))
    assert page.source_entry.get() == original
    page.services.dialog_service.select_folder.assert_not_called()
    page._running = True
    page._set_busy(False)
    click_source(page, "BRANCH")
    assert page.workflow_var.get() == "HO"
    page._running = False
    page._set_busy(False)
    assert page.source_entry.instate(("readonly",) if configured else ("!disabled", "!readonly"))
    assert page.source_browse_button.instate(("disabled",) if configured else ("!disabled",))
    click_source(page, "BRANCH")
    assert page.workflow_var.get() == "BRANCH"
    assert page.source_entry.get() == (str(page._configured_sources["BRANCH"]) if configured else original)


def test_request_does_not_check_filesystem_on_ui_thread(source_page, monkeypatch):
    page, runner = source_page
    page.source_var.set(str(page._configured_sources["HO"]))
    page.start_entry.set_iso("2026-07-01")
    page.end_entry.set_iso("2026-07-31")
    monkeypatch.setattr(Path, "is_dir", Mock(side_effect=AssertionError("UI filesystem access")))
    request = page._request()
    assert request.source_folder == page._configured_sources["HO"]
    assert request.workflow == "HO"


def test_scan_failure_is_shown_for_current_folder(source_page):
    page, runner = source_page
    page.source_var.set(str(page._configured_sources["HO"] / "missing"))
    page.refresh_source()
    runner.complete(0)
    assert "Folder TXT HRIS tidak tersedia" in page.source_summary_var.get()


def test_failed_preflight_unlocks_source_without_starting_upload(source_page):
    page, runner = source_page
    page.source_var.set(str(page._configured_sources["HO"]))
    page.start_entry.set_iso("2026-07-01")
    page.end_entry.set_iso("2026-07-31")
    page.services.hris_service.preflight = Mock(side_effect=ValueError("Folder unavailable"))
    page._start_run = Mock()
    page.run_hris()
    assert page.source_type_choice.instate(("disabled",))
    click_source(page, "BRANCH")
    assert page.workflow_var.get() == "HO"
    runner.complete(0)
    assert page.source_type_choice.instate(("!disabled",))
    assert page.source_entry.instate(("readonly",))
    page._start_run.assert_not_called()
    page.services.dialog_service.confirm.assert_not_called()
