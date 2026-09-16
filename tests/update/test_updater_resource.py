from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shared.update.exceptions import UpdateApplyError
from shared.update.updater_launcher import UpdaterLauncher
from shared.update.updater_resource import (
    UPDATER_EXECUTABLE_NAME,
    default_updater_resource,
)


def test_development_resource_resolution_prefers_built_executable(tmp_path: Path) -> None:
    updater = tmp_path / "dist" / "updater" / UPDATER_EXECUTABLE_NAME
    updater.parent.mkdir(parents=True)
    updater.write_bytes(b"exe")
    (tmp_path / "updater").mkdir()
    (tmp_path / "updater" / "main.py").write_text("print('dev')", encoding="utf-8")

    resource = default_updater_resource(project_root=tmp_path)

    assert resource.path == updater.resolve()
    assert resource.kind == "executable"


def test_development_resource_resolution_falls_back_to_source_script(
    tmp_path: Path,
) -> None:
    source = tmp_path / "updater" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("print('dev')", encoding="utf-8")

    resource = default_updater_resource(project_root=tmp_path)

    assert resource.path == source.resolve()
    assert resource.kind == "python_script"


def test_simulated_meipass_resource_resolution_finds_bundled_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundled = tmp_path / "updater" / UPDATER_EXECUTABLE_NAME
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    resource = default_updater_resource(project_root=tmp_path / "ignored")

    assert resource.path == bundled.resolve()
    assert resource.kind == "executable"


def test_missing_bundled_updater_has_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    with pytest.raises(
        UpdateApplyError,
        match="OAS-K-Updater.exe tidak ditemukan dalam paket aplikasi.",
    ):
        default_updater_resource(project_root=tmp_path / "ignored")


def test_copy_executable_updater_to_runtime_from_file_source(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    app_root.mkdir()
    source = tmp_path / "_MEI12345" / "updater" / UPDATER_EXECUTABLE_NAME
    source.parent.mkdir(parents=True)
    source.write_bytes(b"bundled updater exe")

    runtime = UpdaterLauncher(data_root, updater_source=source).ensure_runtime(
        app_root,
        runtime_id="transaction-1",
    )

    assert runtime.is_file()
    assert runtime.name == UPDATER_EXECUTABLE_NAME
    assert runtime.read_bytes() == source.read_bytes()
    assert data_root.resolve() in runtime.resolve().parents
    assert app_root.resolve() not in runtime.resolve().parents
    assert source.parent.resolve() not in runtime.resolve().parents


def test_python_script_runtime_remains_supported_for_development(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    app_root.mkdir()
    source = tmp_path / "updater" / "main.py"
    source.parent.mkdir()
    source.write_text("print('dev updater')", encoding="utf-8")

    runtime = UpdaterLauncher(data_root, updater_source=source).ensure_runtime(app_root)

    assert runtime.name == "main.py"
    assert runtime.read_text(encoding="utf-8") == "print('dev updater')"
