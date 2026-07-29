from __future__ import annotations

import logging
import time

from PIL import Image

from config.app_config import APP_VERSION, PROJECT_ROOT
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.app import OASKUnifiedApp
from ui.context import AppContext
from ui.services.service_container import build_default_app_services


def _label_texts(widget) -> set[str]:
    texts: set[str] = set()
    for child in widget.winfo_children():
        if child.winfo_class() == "TLabel":
            texts.add(str(child.cget("text")))
        texts.update(_label_texts(child))
    return texts


def test_welcome_png_assets_have_expected_transparent_dimensions() -> None:
    folder = PROJECT_ROOT / "assets" / "icons" / "png"
    with Image.open(folder / "welcome.png") as image:
        assert (image.size, image.mode) == ((500, 500), "RGBA")
    with Image.open(folder / "start_button_pxl.png") as image:
        assert (image.size, image.mode) == ((500, 200), "RGBA")


def test_startup_shows_welcome_splash_with_image_and_copy(
    tk_root,
    tmp_path,
) -> None:
    backend = FakeRegistryBackend()
    services = build_default_app_services(
        tk_root,
        application_version=APP_VERSION,
        project_root=PROJECT_ROOT,
        registry=StorageRegistryService(backend),
        default_data_root=tmp_path / "Data",
    )
    context = AppContext(
        project_root=PROJECT_ROOT,
        assets_path=PROJECT_ROOT / "assets",
        application_version=APP_VERSION,
        logger=logging.getLogger("welcome-splash-test"),
        app_services=services,
    )

    app = OASKUnifiedApp(tk_root, context=context)
    tk_root.update_idletasks()

    assert app._welcome_splash.winfo_exists()
    assert app._welcome_image is not None
    assert app._welcome_image.width() == 140
    assert app._welcome_image.height() == 140
    assert app._welcome_start_image is not None
    assert app._welcome_start_image.width() == 200
    assert app._welcome_start_image.height() == 80
    assert app._welcome_shimmer_job is not None
    title_style = app._welcome_title_label.cget("style")
    glow_style = app._welcome_start_glow.cget("style")
    app._advance_welcome_shimmer()
    assert app._welcome_title_label.cget("style") != title_style
    assert app._welcome_start_glow.cget("style") != glow_style
    texts = _label_texts(app._welcome_splash)
    assert "WELCOME TO" in texts
    assert "OFFICE AUTOMATION SUITE - KARINA" in texts
    assert "BY HR SERVICES" in texts
    assert app._welcome_status_var.get() == (
        "Tekan START atau Enter untuk memulai."
    )
    assert app.navigation.active_page_id is None

    app._start_from_welcome()
    assert not app._welcome_splash.winfo_exists()
    assert app._welcome_shimmer_job is None
    assert app.navigation.active_page_id == "dashboard"
    assert app.startup_database_result.status == "NO_DATABASE"
    deadline = time.monotonic() + 2
    dashboard = app.navigation._cache["dashboard"]
    while dashboard._busy and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(0.01)
    assert not dashboard._busy
    assert app.close()
