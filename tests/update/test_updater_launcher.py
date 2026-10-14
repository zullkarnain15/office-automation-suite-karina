from __future__ import annotations

from pathlib import Path

from shared.update.transaction_store import UpdateTransactionStore
from shared.update.updater_launcher import UpdaterLauncher


def test_updater_runtime_copied_outside_application_root(tmp_path: Path) -> None:
    data_root, app_root, staging = layout(tmp_path)
    source = tmp_path / "source_updater"
    source.mkdir()
    (source / "main.py").write_text("print('updater')", encoding="utf-8")
    launcher = UpdaterLauncher(data_root, updater_source=source)
    runtime = launcher.ensure_runtime(app_root)
    assert runtime.is_file()
    assert app_root not in runtime.resolve().parents
    assert data_root in runtime.resolve().parents


def layout(tmp_path: Path):
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staging = data_root / "update" / "staging" / "v1.1.0"
    (staging / "application").mkdir(parents=True)
    app_root.mkdir()
    (app_root / "OAS-K.exe").write_text("old", encoding="utf-8")
    (staging / "application" / "OAS-K.exe").write_text("new", encoding="utf-8")
    return data_root, app_root, staging
