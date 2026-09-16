"""Optional real-Tk smoke tests; skipped when no display is available."""

from __future__ import annotations

import tkinter as tk
import logging

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.app import OASKUnifiedApp
from ui.constants import APP_TITLE, PAGE_ORDER
from ui.context import AppContext
from ui.services.service_container import build_default_app_services


def test_tk_shell_full_smoke(tk_root: tk.Tk) -> None:
    app = OASKUnifiedApp(tk_root)
    tk_root.update_idletasks()
    assert app.navigation.active_page_id is None
    assert app.navigation.cached_page_ids == ()
    app._start_from_welcome()
    tk_root.update_idletasks()
    assert app.navigation.active_page_id == "dashboard"
    assert app.navigation.cached_page_ids == ("dashboard",)
    assert app.header._title_icons["dashboard"] is not None
    assert app.header.title_icon_label.grid_info()
    assert app.sidebar.menu_ids == PAGE_ORDER
    for page_id in PAGE_ORDER:
        assert app.navigate(page_id)
        assert app.header.title_icon_label.grid_info()
    tk_root.update_idletasks()
    top_levels = [
        child for child in tk_root.winfo_children() if isinstance(child, tk.Toplevel)
    ]
    assert app.navigation.cached_page_ids == PAGE_ORDER
    assert not top_levels
    settings = app.navigation._cache["settings"]
    assert tuple(
        settings.notebook.tab(tab_id, "text")
        for tab_id in settings.notebook.tabs()
        ) == (
            "General",
            "Module Configuration",
            "Import / Export",
            "Storage & Database",
            "Backup & Recovery",
            "Application Update",
            "HRIS Recorder Profiles",
    )
    tk_root.geometry("1100x680")
    tk_root.update_idletasks()
    assert tk_root.title() == APP_TITLE
    assert tk_root.minsize() == (1000, 640)
    assert tk_root.resizable() == (1, 1)
    page = app.navigation._cache["system_health"]
    disposed: list[bool] = []
    page.dispose = lambda: disposed.append(True)
    assert app.close()
    assert disposed == [True]


def test_opening_settings_with_fake_registry_has_zero_side_effects(
    tk_root: tk.Tk, tmp_path, monkeypatch
) -> None:
    data_root = tmp_path / "isolated" / "Data"
    backend = FakeRegistryBackend()
    services = build_default_app_services(
        tk_root,
        application_version=APP_VERSION,
        project_root=PROJECT_ROOT,
        registry=StorageRegistryService(backend),
        default_data_root=data_root,
    )
    calls = []
    guarded_actions = (
        (services.storage_service, "initialize"),
        (services.storage_service, "relocate_to"),
        (services.configuration_service, "preview"),
        (services.configuration_service, "commit"),
        (services.configuration_service, "export"),
        (services.recovery_service, "backup_database"),
        (services.recovery_service, "backup_application_data"),
        (services.recovery_service, "restore"),
        (services.recovery_service, "import_database"),
        (services.recovery_service, "reset"),
    )
    for service, name in guarded_actions:
        monkeypatch.setattr(
            service,
            name,
            lambda *args, _name=name, **kwargs: calls.append(_name),
        )
    context = AppContext(
        project_root=PROJECT_ROOT,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("ui2-zero-side-effect"),
        app_services=services,
    )
    app = OASKUnifiedApp(tk_root, context=context)
    assert app.navigate("settings")
    tk_root.update_idletasks()

    settings = app.navigation._cache["settings"]
    assert tuple(settings.sections) == (
        "General",
        "Module Configuration",
        "Import / Export",
        "Storage & Database",
        "Backup & Recovery",
        "Application Update",
        "HRIS Recorder Profiles",
    )
    assert calls == []
    assert backend.write_count == 0
    assert backend.delete_count == 0
    assert backend.values == {}
    assert not data_root.exists()
    assert not list(tmp_path.rglob("*.db"))
    assert app.close()
