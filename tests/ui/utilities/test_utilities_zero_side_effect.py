from __future__ import annotations

import logging

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.app import OASKUnifiedApp
from ui.context import AppContext
from ui.services.service_container import build_default_app_services


def test_opening_utilities_landing_has_zero_side_effects(
    tk_root, tmp_path, monkeypatch
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
    forbidden = []
    for service in (
        services.utilities_service,
        services.comparison_result_service,
        services.attachment_consolidation_service,
    ):
        monkeypatch.setattr(
            service,
            "load_defaults",
            lambda _name=type(service).__name__: forbidden.append(_name),
        )
    for service, name in (
        (services.comparison_result_service, "preflight"),
        (services.comparison_result_service, "run_job"),
        (services.attachment_consolidation_service, "preflight"),
        (services.attachment_consolidation_service, "run_job"),
    ):
        monkeypatch.setattr(
            service,
            name,
            lambda *args, _name=name, **kwargs: forbidden.append(_name),
        )
    context = AppContext(
        project_root=PROJECT_ROOT,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("ui7-zero-side-effect"),
        app_services=services,
    )
    app = OASKUnifiedApp(tk_root, context=context)
    assert app.navigate("utilities")
    tk_root.update_idletasks()
    page = app.navigation._cache["utilities"]
    assert page._feature is None
    assert forbidden == []
    assert backend.write_count == 0 and backend.delete_count == 0
    assert not data_root.exists()
    assert not list(tmp_path.rglob("*.db"))
    assert app.close()
