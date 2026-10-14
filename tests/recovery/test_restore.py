"""Restore, rollback, source preservation, Registry, and audit tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.recovery import (
    ApplicationDataBackupRequest,
    ApplicationDataBackupService,
    ImportDatabaseRequest,
    RestoreRequest,
    RestoreService,
)
from shared.recovery.audit_service import sha256_file
from shared.recovery.staging_manager import StagingManager
from shared.storage.constants import REGISTRY_KEY
from shared.storage.exceptions import RegistryAccessError
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService


def _version(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT application_version FROM database_metadata WHERE metadata_id=1"
        ).fetchone()[0]


def test_restore_database_succeeds(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=True)
    )
    assert result.success
    assert _version(result.active_database) == "db4-candidate"


def test_restore_current_database_backed_up(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=True)
    )
    assert result.success
    assert result.pre_operation_backup is not None
    assert result.pre_operation_backup.is_file()
    assert _version(result.pre_operation_backup) == "db4-active"


def test_restore_requires_confirmation(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=False)
    )
    assert not result.success
    assert "confirm" in result.errors[0]


def test_restore_invalid_candidate_rejected(
    data_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad.db"
    source.write_bytes(b"bad")
    result = RestoreService().restore(
        RestoreRequest(source, data_root, confirm=True)
    )
    assert not result.success
    assert _version(result.active_database) == "db4-active"


def test_restore_failure_rolls_back(
    data_root: Path,
    candidate_database: Path,
) -> None:
    class FailAfterActivation(StagingManager):
        @staticmethod
        def activate(staged_database, active_database, rollback_database):
            StagingManager.activate(
                staged_database, active_database, rollback_database
            )
            raise RuntimeError("injected activation failure")

    result = RestoreService(
        staging_manager=FailAfterActivation()
    ).restore(RestoreRequest(candidate_database, data_root, confirm=True))
    assert not result.success
    assert result.rolled_back
    assert _version(result.active_database) == "db4-active"


def test_restore_source_not_deleted(
    data_root: Path,
    candidate_database: Path,
) -> None:
    before = sha256_file(candidate_database)
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=True)
    )
    assert result.success
    assert candidate_database.is_file()
    assert sha256_file(candidate_database) == before


def test_restore_zip_and_profiles(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    profile = layout.hris_recorder_profiles_root / "recorded.json"
    profile.write_text('{"name": "restored"}', encoding="utf-8")
    backup = ApplicationDataBackupService().backup(
        ApplicationDataBackupRequest(
            data_root, layout.backup_root, "db4-test"
        )
    )
    assert backup.backup_path is not None
    profile.unlink()
    result = RestoreService().restore(
        RestoreRequest(backup.backup_path, data_root, confirm=True)
    )
    assert result.success
    assert profile.is_file()
    assert result.recorder_profiles_restored == 1


def test_registry_updated_only_after_success(
    data_root: Path,
    candidate_database: Path,
    fake_backend: FakeRegistryBackend,
    fake_registry: StorageRegistryService,
) -> None:
    result = RestoreService(fake_registry).restore(
        RestoreRequest(
            candidate_database,
            data_root,
            confirm=True,
            update_registry=True,
        )
    )
    assert result.success and result.registry_updated
    assert fake_backend.write_count == 1
    assert REGISTRY_KEY in fake_backend.values


def test_invalid_restore_does_not_write_registry(
    data_root: Path,
    tmp_path: Path,
    fake_backend: FakeRegistryBackend,
    fake_registry: StorageRegistryService,
) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"bad")
    result = RestoreService(fake_registry).restore(
        RestoreRequest(invalid, data_root, True, update_registry=True)
    )
    assert not result.success
    assert fake_backend.write_count == 0


def test_registry_failure_rolls_back(
    data_root: Path,
    candidate_database: Path,
) -> None:
    class RejectWrites(FakeRegistryBackend):
        def write_values(self, key, values):
            raise RegistryAccessError("injected Registry failure")

    registry = StorageRegistryService(RejectWrites())
    result = RestoreService(registry).restore(
        RestoreRequest(
            candidate_database,
            data_root,
            confirm=True,
            update_registry=True,
        )
    )
    assert not result.success
    assert result.rolled_back
    assert _version(result.active_database) == "db4-active"
    assert not list(Path(data_root).rglob("*.json.pointer"))


def test_restore_success_audited(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=True)
    )
    with sqlite3.connect(result.active_database) as connection:
        history = connection.execute(
            "SELECT COUNT(*) FROM backup_history "
            "WHERE action_type='RESTORE_FROM_BACKUP' AND status='SUCCESS'"
        ).fetchone()[0]
        audit = connection.execute(
            "SELECT COUNT(*) FROM configuration_audit "
            "WHERE setting_scope='DATABASE_RECOVERY'"
        ).fetchone()[0]
    assert history == 1 and audit == 1


def test_restore_failure_audited(data_root: Path, tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"bad")
    result = RestoreService().restore(
        RestoreRequest(invalid, data_root, confirm=True)
    )
    assert not result.success
    with sqlite3.connect(result.active_database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM backup_history "
            "WHERE action_type='RESTORE_FROM_BACKUP' AND status='FAILED'"
        ).fetchone()[0]
    assert count == 1


def test_secret_operator_is_redacted(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(
            candidate_database,
            data_root,
            confirm=True,
            operator="secret=my-password",
        )
    )
    with sqlite3.connect(result.active_database) as connection:
        operators = [
            row[0]
            for row in connection.execute(
                "SELECT operator FROM configuration_audit"
            )
        ]
    assert operators == ["[REDACTED]"]


def test_staging_cleanup_after_success(
    data_root: Path,
    candidate_database: Path,
) -> None:
    result = RestoreService().restore(
        RestoreRequest(candidate_database, data_root, confirm=True)
    )
    base = (
        resolve_storage_layout(data_root).diagnostics_root
        / "recovery_staging"
    )
    assert result.success
    assert not list(base.iterdir())


def test_staging_cleanup_after_failure(
    data_root: Path,
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"bad")
    result = RestoreService().restore(
        RestoreRequest(invalid, data_root, confirm=True)
    )
    base = (
        resolve_storage_layout(data_root).diagnostics_root
        / "recovery_staging"
    )
    assert not result.success
    assert not list(base.iterdir())


def test_restore_module_does_not_import_engine_or_gui() -> None:
    import subprocess
    import sys

    code = (
        "import sys; import shared.recovery; "
        "assert 'attendance.engine' not in sys.modules; "
        "assert 'unified_ui.main_window' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_unused_import_request_symbol_keeps_public_contract() -> None:
    assert ImportDatabaseRequest.__name__ == "ImportDatabaseRequest"
