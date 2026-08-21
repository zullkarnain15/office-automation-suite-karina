"""Settings section, confirmation, busy-state, and no-auto-run contracts."""

from __future__ import annotations

import ast
from types import SimpleNamespace

from config.app_config import PROJECT_ROOT
from ui.dialogs.typed_confirmation_dialog import typed_value_matches
from ui.pages.settings_page import SettingsPage


class _Widget:
    def __init__(self) -> None:
        self.states = []

    def winfo_exists(self) -> bool:
        return True

    def configure(self, **values) -> None:
        self.states.append(values["state"])


class _DeadWidget(_Widget):
    def winfo_exists(self) -> bool:
        return False


class _Progress:
    def __init__(self) -> None:
        self.events = []

    def start(self, message) -> None:
        self.events.append(("start", message))

    def stop(self) -> None:
        self.events.append(("stop", None))


class _Runner:
    def __init__(self) -> None:
        self.on_done = None

    def submit(self, function, *, on_done, on_progress, cancellable):
        self.on_done = on_done
        return object()


def _task_page():
    page = object.__new__(SettingsPage)
    page._busy = False
    page._destructive_busy = False
    page._action_widgets = [_Widget()]
    page.progress_panel = _Progress()
    page.context = SimpleNamespace(
        set_status=lambda message: None,
        logger=SimpleNamespace(error=lambda *args: None),
    )
    runner = _Runner()
    errors = []
    page.services = SimpleNamespace(
        task_runner=runner,
        dialog_service=SimpleNamespace(
            warning=lambda *args: None,
            error=lambda *args: errors.append(args),
        ),
    )
    return page, runner, errors


def test_settings_declares_sections_in_final_order() -> None:
    source = (
        PROJECT_ROOT / "ui" / "pages" / "settings_page.py"
    ).read_text(encoding="utf-8")
    titles = (
        "General",
        "Module Configuration",
        "Import / Export",
        "Storage & Database",
        "Backup & Recovery",
        "Application Update",
        "HRIS Recorder Profiles",
    )
    declarations = source[source.index("sections = (") :]
    for title in titles:
        assert title in declarations
    assert [declarations.index(f'("{title}"') for title in titles] == sorted(
        declarations.index(f'("{title}"') for title in titles
    )


def test_settings_sections_are_split_into_modules() -> None:
    root = PROJECT_ROOT / "ui" / "pages" / "settings"
    expected = {
        "general_section.py",
        "module_configuration_section.py",
        "storage_section.py",
        "configuration_section.py",
        "recovery_section.py",
        "application_update_section.py",
        "recorder_profiles_section.py",
    }
    assert expected <= {path.name for path in root.glob("*.py")}


def test_opening_settings_has_no_auto_action_calls() -> None:
    path = PROJECT_ROOT / "ui" / "pages" / "settings_page.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    init = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    calls = {
        node.func.attr
        for node in ast.walk(init)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls.isdisjoint(
        {"initialize", "relocate", "restore", "reset", "commit", "export"}
    )


def test_reset_typed_confirmation_is_case_sensitive() -> None:
    assert typed_value_matches("RESET", "RESET")
    assert not typed_value_matches("reset", "RESET")


def test_destructive_busy_blocks_navigation() -> None:
    page = object.__new__(SettingsPage)
    page._destructive_busy = True
    assert not page.can_navigate_away()
    page._destructive_busy = False
    assert page.can_navigate_away()


def test_busy_state_recovers_after_success() -> None:
    page, runner, errors = _task_page()
    values = []
    page.run_task(
        lambda: 42,
        on_success=values.append,
        message="Working",
        destructive=True,
    )
    assert page.is_busy and not page.can_navigate_away()
    runner.on_done(SimpleNamespace(success=True, value=42, error=None))
    assert not page.is_busy and page.can_navigate_away()
    assert page._action_widgets[0].states == ["disabled", "normal"]
    assert values == [42]
    assert not errors


def test_busy_state_recovers_after_failure() -> None:
    page, runner, errors = _task_page()
    page.run_task(
        lambda: None,
        on_success=lambda value: None,
        message="Working",
        destructive=True,
    )
    runner.on_done(SimpleNamespace(success=False, value=None, error="boom"))
    assert not page.is_busy and page.can_navigate_away()
    assert page._action_widgets[0].states == ["disabled", "normal"]
    assert errors and errors[0][1] == "boom"


def test_busy_state_ignores_destroyed_registered_widgets() -> None:
    page, runner, errors = _task_page()
    live = page._action_widgets[0]
    page._action_widgets = [_DeadWidget(), live]
    values = []
    page.run_task(
        lambda: 42,
        on_success=values.append,
        message="Working",
    )
    runner.on_done(SimpleNamespace(success=True, value=42, error=None))
    assert not page.is_busy
    assert page._action_widgets == [live]
    assert live.states == ["disabled", "normal"]
    assert values == [42]
    assert not errors


def test_recovery_ui_contains_no_automatic_reset() -> None:
    source = (
        PROJECT_ROOT
        / "ui"
        / "pages"
        / "settings"
        / "recovery_section.py"
    ).read_text(encoding="utf-8")
    assert "typed_confirm" in source
    assert "Konfirmasi Reset Kedua" in source


def test_configuration_preview_and_commit_are_separate_actions() -> None:
    source = (
        PROJECT_ROOT
        / "ui"
        / "pages"
        / "settings"
        / "configuration_section.py"
    ).read_text(encoding="utf-8")
    assert "Periksa Konfigurasi" in source
    assert "Terapkan Konfigurasi" in source
    assert "Build Import Preview" not in source
    assert "Commit Preview Modules" not in source


def test_settings_on_show_auto_refreshes_read_only_state() -> None:
    source = (
        PROJECT_ROOT / "ui" / "pages" / "settings_page.py"
    ).read_text(encoding="utf-8")
    assert "resolve_status" in source
    assert "load_global_settings" in source
    assert "load_module_global_usage" in source
    assert "load_summaries" in source
    on_show_source = source[source.index("def on_show") :]
    assert ".initialize(" not in on_show_source
    assert ".save_global_settings(" not in on_show_source
    assert ".commit_preview(" not in on_show_source
    assert ".export(" not in on_show_source


def test_pages_do_not_import_engines() -> None:
    root = PROJECT_ROOT / "ui" / "pages" / "settings"
    forbidden = {"attendance", "outlook", "outlook_revisi", "hris", "utilities"}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = {
            node.module.partition(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert roots.isdisjoint(forbidden)
