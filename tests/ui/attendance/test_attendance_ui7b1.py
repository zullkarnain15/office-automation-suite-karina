from __future__ import annotations

import logging

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.app import OASKUnifiedApp
from ui.context import AppContext
from ui.services.service_container import build_default_app_services


def _test_app(tk_root, tmp_path):
    backend = FakeRegistryBackend()
    data_root = tmp_path / "isolated" / "Data"
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
        logger=logging.getLogger("ui7b1-attendance"),
        app_services=services,
    )
    return OASKUnifiedApp(tk_root, context=context), services, backend, data_root


def test_opening_attendance_has_zero_operational_side_effects(
    tk_root, tmp_path, monkeypatch
) -> None:
    app, services, backend, data_root = _test_app(tk_root, tmp_path)
    calls = []
    monkeypatch.setattr(
        services.attendance_service.adapter,
        "validate_configuration",
        lambda *args, **kwargs: calls.append("adapter"),
    )
    monkeypatch.setattr(
        services.attendance_service,
        "preflight",
        lambda *args, **kwargs: calls.append("preflight"),
    )
    monkeypatch.setattr(
        services.attendance_service,
        "run_job",
        lambda *args, **kwargs: calls.append("run"),
    )
    assert app.navigate("attendance")
    for _ in range(10):
        tk_root.update()
    assert calls == []
    assert backend.write_count == 0 and backend.delete_count == 0
    assert not data_root.exists()
    assert not list(tmp_path.rglob("*.db"))
    assert app.close()


def test_normal_workflow_and_run_are_visible_at_minimum_size(tk_root, tmp_path) -> None:
    app, _services, _backend, _data_root = _test_app(tk_root, tmp_path)
    tk_root.geometry("1000x640")
    assert app.navigate("attendance")
    for _ in range(10):
        tk_root.update()
    page = app.navigation._cache["attendance"]
    assert app.sidebar.master.winfo_width() == 170
    assert page.run_button.winfo_rooty() + page.run_button.winfo_height() <= (
        tk_root.winfo_rooty() + tk_root.winfo_height()
    )
    assert abs(page.validate_button.winfo_rooty() - page.run_button.winfo_rooty()) <= 1
    workflow_buttons = page.workflow_choices.winfo_children()
    assert len(workflow_buttons) == 2
    assert workflow_buttons[0].winfo_rooty() == workflow_buttons[1].winfo_rooty()
    assert page._operational_mode == "compact"
    assert page.period_section.grid_info()["row"] == 0
    assert page.workflow_section.grid_info()["row"] == 0
    assert page.output_section.grid_info()["row"] == 0
    assert page.log_text.cget("height") == 5
    assert not page.result_panel.winfo_manager()
    assert not page.advanced_frame.winfo_manager()
    assert not any(widget.winfo_class() == "Canvas" for widget in page.winfo_children())
    assert app.close()


def test_log_expands_and_returns_to_compact_height(tk_root, tmp_path) -> None:
    app, _services, _backend, _data_root = _test_app(tk_root, tmp_path)
    assert app.navigate("attendance")
    page = app.navigation._cache["attendance"]
    page.toggle_log()
    assert page.log_text.cget("height") == 10
    assert page.log_expand_button.cget("text") == "Perkecil Log"
    page.toggle_log()
    assert page.log_text.cget("height") == 5
    assert app.close()
