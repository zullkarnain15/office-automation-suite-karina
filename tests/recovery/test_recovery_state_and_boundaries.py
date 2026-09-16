"""Recovery recommendations, manual CLI guardrails, and sprint boundaries."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from shared.recovery import CandidateValidator, RecoveryAction, RecoveryService
from shared.recovery.constants import RecoveryStatus
from shared.storage.models import StartupStorageResolution, StartupStorageStatus
from shared.storage.path_resolver import resolve_storage_layout
from tools.recovery_test.recovery_cli import build_parser


def _startup(
    status: StartupStorageStatus,
    data_root: Path,
) -> StartupStorageResolution:
    return StartupStorageResolution(
        status=status,
        data_root=data_root,
        database_path=resolve_storage_layout(data_root).database_path,
    )


def test_recovery_state_healthy(data_root: Path) -> None:
    database = CandidateValidator().validate(
        resolve_storage_layout(data_root).database_path
    )
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.READY, data_root),
        database,
        backups_available=False,
    )
    assert state.primary_status == RecoveryStatus.HEALTHY
    assert state.recommendations[0].action == RecoveryAction.CANCEL


def test_recovery_state_database_missing(tmp_path: Path) -> None:
    root = tmp_path / "missing-root"
    database = CandidateValidator().validate(
        resolve_storage_layout(root).database_path
    )
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, root),
        database,
        backups_available=False,
    )
    assert state.primary_status == RecoveryStatus.DATABASE_MISSING
    assert RecoveryStatus.NO_BACKUP_AVAILABLE in state.statuses


def test_recovery_state_database_invalid(
    tmp_path: Path,
) -> None:
    root = tmp_path / "invalid-root"
    database = resolve_storage_layout(root).database_path
    database.parent.mkdir(parents=True)
    database.write_bytes(b"invalid")
    candidate = CandidateValidator().validate(database)
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, root),
        candidate,
        backups_available=False,
    )
    assert state.primary_status == RecoveryStatus.DATABASE_INVALID


def test_recommend_restore_last_backup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing"
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, root),
        None,
        backups_available=True,
    )
    actions = [item.action for item in state.recommendations]
    assert RecoveryAction.RESTORE_LAST_BACKUP in actions


def test_recommend_import_existing_database(
    tmp_path: Path,
) -> None:
    root = tmp_path / "missing"
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, root),
        None,
        backups_available=False,
    )
    assert RecoveryAction.IMPORT_EXISTING_DATABASE in {
        item.action for item in state.recommendations
    }


def test_recommend_reset_to_default(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, root),
        None,
        backups_available=False,
    )
    assert RecoveryAction.RESET_TO_DEFAULT in {
        item.action for item in state.recommendations
    }


def test_registry_pointer_invalid_status(data_root: Path) -> None:
    database = CandidateValidator().validate(
        resolve_storage_layout(data_root).database_path
    )
    state = RecoveryService().assess(
        _startup(StartupStorageStatus.RECOVERY_REQUIRED, data_root),
        database,
        backups_available=True,
        registry_pointer_valid=False,
    )
    assert state.primary_status == RecoveryStatus.REGISTRY_POINTER_INVALID


def test_recovery_service_has_no_action_methods() -> None:
    service = RecoveryService()
    assert not hasattr(service, "restore")
    assert not hasattr(service, "reset")
    assert not hasattr(service, "import_database")


def test_cli_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_cli_requires_explicit_data_root() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["backup-db"])


def test_cli_reset_has_separate_confirmation_flag(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "reset-default",
            "--data-root",
            str(tmp_path),
            "--application-version",
            "test",
            "--confirm-reset",
        ]
    )
    assert args.confirm_reset


def test_cli_registry_flags_default_false(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "restore",
            "--data-root",
            str(tmp_path),
            "--source",
            str(tmp_path / "backup.db"),
        ]
    )
    assert not args.write_registry
    assert not args.confirm_registry_write


def test_no_engine_or_gui_imports() -> None:
    code = (
        "import sys; import shared.recovery; "
        "forbidden=('attendance.engine','hris.engine','outlook.engine','unified_ui'); "
        "assert not any(n == f or n.startswith(f + '.') "
        "for n in sys.modules for f in forbidden)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_no_json_pointer_files(data_root: Path) -> None:
    assert not list(data_root.rglob("*.json.pointer"))
    assert not list(data_root.rglob("storage_pointer.json"))


def test_tests_use_temporary_root(data_root: Path) -> None:
    assert "pytest-" in str(data_root).lower()
    assert data_root.resolve() != Path("D:/OAS-K/Data").resolve()
