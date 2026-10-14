"""Manual DB4 recovery CLI; all paths and destructive confirmations are explicit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.recovery import (  # noqa: E402
    ApplicationDataBackupRequest,
    ApplicationDataBackupService,
    BackupReason,
    CandidateValidator,
    DatabaseBackupRequest,
    DatabaseBackupService,
    ImportDatabaseRequest,
    ImportDatabaseService,
    RecoveryService,
    ResetDatabaseRequest,
    ResetService,
    RestoreRequest,
    RestoreService,
)
from shared.storage.models import (  # noqa: E402
    StartupStorageResolution,
    StartupStorageStatus,
)
from shared.storage.path_resolver import resolve_storage_layout  # noqa: E402
from shared.storage.registry import (  # noqa: E402
    StorageRegistryService,
    WindowsRegistryBackend,
)
from shared.storage.storage_validator import validate_data_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OAS-K DB4 recovery test CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_db = subparsers.add_parser("backup-db")
    _data_root(backup_db)
    backup_db.add_argument("--reason", choices=[item.value for item in BackupReason], default="MANUAL")

    backup_app = subparsers.add_parser("backup-app-data")
    _data_root(backup_app)
    backup_app.add_argument("--application-version", required=True)
    backup_app.add_argument("--include-logs", action="store_true")
    backup_app.add_argument("--include-diagnostics", action="store_true")

    validate = subparsers.add_parser("validate-candidate")
    _data_root(validate)
    validate.add_argument("--candidate", type=Path, required=True)

    restore = subparsers.add_parser("restore")
    _data_root(restore)
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--confirm", action="store_true")
    restore.add_argument("--no-restore-profiles", action="store_true")
    _registry_flags(restore)

    import_db = subparsers.add_parser("import-db")
    _data_root(import_db)
    import_db.add_argument("--source", type=Path, required=True)
    import_db.add_argument("--confirm", action="store_true")
    _registry_flags(import_db)

    reset = subparsers.add_parser("reset-default")
    _data_root(reset)
    reset.add_argument("--application-version", required=True)
    reset.add_argument("--confirm-reset", action="store_true")
    _registry_flags(reset)

    status = subparsers.add_parser("recovery-status")
    _data_root(status)
    status.add_argument("--backups-available", action="store_true")
    return parser


def _data_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-root", type=Path, required=True)


def _registry_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force-without-prebackup", action="store_true")
    parser.add_argument("--write-registry", action="store_true")
    parser.add_argument("--confirm-registry-write", action="store_true")


def _registry(args: argparse.Namespace) -> StorageRegistryService | None:
    write = bool(getattr(args, "write_registry", False))
    confirmed = bool(getattr(args, "confirm_registry_write", False))
    if write != confirmed:
        raise ValueError(
            "Registry writes require both --write-registry and "
            "--confirm-registry-write."
        )
    if not write:
        return None
    return StorageRegistryService(WindowsRegistryBackend())


def run(args: argparse.Namespace) -> Any:
    root = args.data_root.expanduser()
    layout = resolve_storage_layout(root)
    if args.command == "backup-db":
        return DatabaseBackupService().backup(
            DatabaseBackupRequest(
                layout.database_path,
                layout.backup_root,
                BackupReason(args.reason),
            )
        )
    if args.command == "backup-app-data":
        return ApplicationDataBackupService().backup(
            ApplicationDataBackupRequest(
                root,
                layout.backup_root,
                args.application_version,
                include_logs=args.include_logs,
                include_diagnostics=args.include_diagnostics,
            )
        )
    if args.command == "validate-candidate":
        return CandidateValidator().validate(args.candidate)
    if args.command == "restore":
        registry = _registry(args)
        return RestoreService(registry).restore(
            RestoreRequest(
                args.source,
                root,
                confirm=args.confirm,
                restore_recorder_profiles=not args.no_restore_profiles,
                force_without_prebackup=args.force_without_prebackup,
                update_registry=registry is not None,
            )
        )
    if args.command == "import-db":
        registry = _registry(args)
        return ImportDatabaseService(registry).import_database(
            ImportDatabaseRequest(
                args.source,
                root,
                confirm=args.confirm,
                force_without_prebackup=args.force_without_prebackup,
                update_registry=registry is not None,
            )
        )
    if args.command == "reset-default":
        registry = _registry(args)
        return ResetService(registry).reset(
            ResetDatabaseRequest(
                root,
                args.application_version,
                confirm=args.confirm_reset,
                force_without_prebackup=args.force_without_prebackup,
                update_registry=registry is not None,
            )
        )
    if args.command == "recovery-status":
        storage_validation = validate_data_root(root)
        if storage_validation.database_valid:
            status = StartupStorageStatus.READY
        elif storage_validation.database_exists:
            status = StartupStorageStatus.RECOVERY_REQUIRED
        else:
            status = StartupStorageStatus.INVALID_LOCATION
        startup = StartupStorageResolution(
            status=status,
            data_root=root,
            database_path=layout.database_path,
            validation=storage_validation,
            warnings=storage_validation.warnings,
            errors=storage_validation.errors,
        )
        candidate = CandidateValidator().validate(layout.database_path)
        return RecoveryService().assess(
            startup,
            candidate,
            backups_available=args.backups_available,
            registry_pointer_valid=True,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unable to serialize {type(value).__name__}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        parser.error(str(exc))
    print(json.dumps(result, default=_json_default, indent=2))
    return 0 if getattr(result, "success", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
