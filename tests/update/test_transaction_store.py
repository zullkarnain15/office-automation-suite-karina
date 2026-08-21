from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.update.exceptions import UpdateTransactionError
from shared.update.transaction_store import UpdateTransactionStore


def test_transaction_atomic_write_read(tmp_path: Path) -> None:
    data_root, app_root, staging = layout(tmp_path)
    store = UpdateTransactionStore(data_root)
    transaction = store.create(
        current_version="1.0.0",
        target_version="1.1.0",
        package_path=tmp_path / "package.zip",
        package_sha256="abc",
        staging_path=staging,
        application_root=app_root,
        database_backup_path=data_root / "backup" / "database" / "backup.db",
        entry_executable="OAS-K.exe",
    )
    assert transaction.transaction_path is not None
    loaded = store.load(transaction.transaction_path)
    assert loaded.transaction_id == transaction.transaction_id
    assert loaded.status == "STAGED"
    assert not list(transaction.transaction_path.parent.glob("*.tmp"))


def test_invalid_transaction_path_rejected(tmp_path: Path) -> None:
    store = UpdateTransactionStore(tmp_path / "data")
    outside = tmp_path / "elsewhere" / "transaction.json"
    outside.parent.mkdir()
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(UpdateTransactionError):
        store.load(outside)


def test_application_root_equals_data_root_rejected(tmp_path: Path) -> None:
    data_root, _app_root, staging = layout(tmp_path)
    store = UpdateTransactionStore(data_root)
    with pytest.raises(UpdateTransactionError):
        store.create(
            current_version="1.0.0",
            target_version="1.1.0",
            package_path=tmp_path / "package.zip",
            package_sha256="abc",
            staging_path=staging,
            application_root=data_root,
            database_backup_path=data_root / "backup.db",
            entry_executable="OAS-K.exe",
        )


def test_staging_and_rollback_outside_update_directory_rejected(tmp_path: Path) -> None:
    data_root, app_root, _staging = layout(tmp_path)
    store = UpdateTransactionStore(data_root)
    with pytest.raises(UpdateTransactionError):
        store.create(
            current_version="1.0.0",
            target_version="1.1.0",
            package_path=tmp_path / "package.zip",
            package_sha256="abc",
            staging_path=tmp_path / "outside_staging",
            application_root=app_root,
            database_backup_path=data_root / "backup.db",
            entry_executable="OAS-K.exe",
        )


def test_latest_non_terminal_detects_interrupted_applying(tmp_path: Path) -> None:
    data_root, app_root, staging = layout(tmp_path)
    store = UpdateTransactionStore(data_root)
    transaction = store.create(
        current_version="1.0.0",
        target_version="1.1.0",
        package_path=tmp_path / "package.zip",
        package_sha256="abc",
        staging_path=staging,
        application_root=app_root,
        database_backup_path=data_root / "backup.db",
        entry_executable="OAS-K.exe",
    )
    store.update_status(transaction, "APPLYING")
    assert store.latest_non_terminal().status == "APPLYING"


def layout(tmp_path: Path):
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staging = data_root / "update" / "staging" / "v1.1.0"
    (staging / "application").mkdir(parents=True)
    app_root.mkdir()
    (app_root / "OAS-K.exe").write_text("old", encoding="utf-8")
    (staging / "application" / "OAS-K.exe").write_text("new", encoding="utf-8")
    (data_root / "backup" / "database").mkdir(parents=True)
    return data_root, app_root, staging
