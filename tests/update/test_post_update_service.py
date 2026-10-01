from __future__ import annotations

from pathlib import Path

from shared.update.post_update_service import PostUpdateService
from shared.update.transaction_store import UpdateTransactionStore


def test_recovery_mode_recommends_restore_when_state_ambiguous(tmp_path: Path) -> None:
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
    store.update_status(transaction, "APPLICATION_REPLACED")

    recovery = PostUpdateService(data_root).detect_interrupted_transaction()
    assert recovery is not None
    assert recovery.recommendation == "Restore Previous Application"


def layout(tmp_path: Path):
    data_root = tmp_path / "data"
    app_root = tmp_path / "app"
    staging = data_root / "update" / "staging" / "v1.1.0"
    (staging / "application").mkdir(parents=True)
    app_root.mkdir()
    (app_root / "OAS-K.exe").write_text("old", encoding="utf-8")
    (staging / "application" / "OAS-K.exe").write_text("new", encoding="utf-8")
    return data_root, app_root, staging
