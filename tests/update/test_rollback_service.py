from __future__ import annotations

from pathlib import Path

from updater.application_replacer import backup_application, replace_application
from updater.rollback_service import restore_previous_application


def test_rollback_restores_old_application_and_preserves_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staged = data_root / "update" / "staging" / "v1.1.0" / "application"
    rollback = data_root / "update" / "rollback" / "tx"
    app_root.mkdir(parents=True)
    staged.mkdir(parents=True)
    (app_root / "OAS-K.exe").write_text("old", encoding="utf-8")
    (staged / "OAS-K.exe").write_text("new", encoding="utf-8")
    database = data_root / "database" / "OAS-K.db"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"database")

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
    restore_previous_application(
        application_root=app_root,
        rollback_path=rollback,
        data_root=data_root,
        entry_executable="OAS-K.exe",
    )

    assert (app_root / "OAS-K.exe").read_text(encoding="utf-8") == "old"
    assert database.read_bytes() == b"database"
