from __future__ import annotations

from pathlib import Path

import pytest

from updater.application_replacer import (
    ApplicationReplacementError,
    backup_application,
    replace_application,
)


def test_backup_application_succeeds_and_preserves_data_root(tmp_path: Path) -> None:
    data_root, app_root, staged, rollback = layout(tmp_path)
    profile = data_root / "recorder_profiles" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text("profile", encoding="utf-8")
    backup = backup_application(
        application_root=app_root,
        rollback_path=rollback,
        data_root=data_root,
        entry_executable="OAS-K.exe",
    )
    assert (backup / "OAS-K.exe").read_text(encoding="utf-8") == "old"
    assert profile.read_text(encoding="utf-8") == "profile"


def test_staged_executable_missing_rejected(tmp_path: Path) -> None:
    data_root, app_root, staged, rollback = layout(tmp_path)
    (staged / "OAS-K.exe").unlink()
    with pytest.raises(ApplicationReplacementError):
        replace_application(
            application_root=app_root,
            staged_application_path=staged,
            rollback_path=rollback,
            data_root=data_root,
            entry_executable="OAS-K.exe",
        )


def test_replacement_succeeds(tmp_path: Path) -> None:
    data_root, app_root, staged, rollback = layout(tmp_path)
    backup_application(
        application_root=app_root,
        rollback_path=rollback,
        data_root=data_root,
        entry_executable="OAS-K.exe",
    )
    replace_application(
        application_root=app_root,
        staged_application_path=staged,
        rollback_path=rollback,
        data_root=data_root,
        entry_executable="OAS-K.exe",
    )
    assert (app_root / "OAS-K.exe").read_text(encoding="utf-8") == "new"
    assert (rollback / "application" / "OAS-K.exe").read_text(encoding="utf-8") == "old"


def test_application_root_equals_data_root_rejected_by_replacer(tmp_path: Path) -> None:
    data_root, _app_root, staged, rollback = layout(tmp_path)
    with pytest.raises(ApplicationReplacementError):
        replace_application(
            application_root=data_root,
            staged_application_path=staged,
            rollback_path=rollback,
            data_root=data_root,
            entry_executable="OAS-K.exe",
        )


def layout(tmp_path: Path):
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staged = data_root / "update" / "staging" / "v1.1.0" / "application"
    rollback = data_root / "update" / "rollback" / "tx"
    app_root.mkdir(parents=True)
    staged.mkdir(parents=True)
    (app_root / "OAS-K.exe").write_text("old", encoding="utf-8")
    (app_root / "assets").mkdir()
    (app_root / "assets" / "logo.txt").write_text("asset", encoding="utf-8")
    (staged / "OAS-K.exe").write_text("new", encoding="utf-8")
    return data_root, app_root, staged, rollback
