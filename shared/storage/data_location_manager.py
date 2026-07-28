"""Controlled copy-and-validate Data Root relocation."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from shared.database import BackupManager, DatabaseValidator
from shared.storage.models import (
    DataLocationChangeRequest,
    DataLocationChangeResult,
)
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.recorder_profile_manager import (
    to_relative_profile_path,
    validate_profile_reference,
)
from shared.storage.registry.windows_registry import StorageRegistryService
from shared.storage.storage_bootstrap import initialize_data_root
from shared.storage.storage_validator import validate_data_root

logger = logging.getLogger(__name__)


class DataLocationManager:
    def __init__(
        self,
        registry: StorageRegistryService,
        *,
        backup_manager: BackupManager | None = None,
        database_validator: DatabaseValidator | None = None,
    ) -> None:
        self.registry = registry
        self.backup_manager = backup_manager or BackupManager()
        self.database_validator = (
            database_validator or DatabaseValidator()
        )

    def change_data_location(
        self,
        request: DataLocationChangeRequest,
    ) -> DataLocationChangeResult:
        source = resolve_storage_layout(request.current_data_root)
        target = resolve_storage_layout(request.target_data_root)
        warnings: list[str] = []
        errors: list[str] = []
        database_copied = False
        profiles_copied = 0
        output_copied = False
        logs_copied = False
        registry_updated = False
        registry_write_attempted = False
        new_database_created = False
        temp_database = target.database_root / ".OAS-K.relocation.tmp.db"
        previous_target = target.database_root / ".OAS-K.pre-relocation.db"
        old_pointer = None

        logger.info(
            "Data location relocation started: %s -> %s",
            source.data_root,
            target.data_root,
        )
        try:
            if source.data_root.resolve() == target.data_root.resolve():
                raise ValueError("Source and target Data Root must differ.")
            source_validation = validate_data_root(
                source.data_root,
                database_validator=self.database_validator,
            )
            if (
                not source_validation.database_exists
                or not source_validation.database_valid
            ):
                raise ValueError("Source database is missing or invalid.")
            target_validation = validate_data_root(
                target.data_root,
                database_validator=self.database_validator,
            )
            if not target_validation.can_initialize:
                raise ValueError(
                    "Target Data Root is not safe: "
                    + "; ".join(target_validation.errors)
                )
            initialize_data_root(target.data_root)

            if request.copy_database:
                if (
                    target.database_path.exists()
                    and not request.overwrite_target_database
                ):
                    raise FileExistsError(
                        "Target database exists; explicit overwrite is required."
                    )
                temp_database.unlink(missing_ok=True)
                self.backup_manager.create_backup(
                    source.database_path,
                    temp_database,
                )
                if not self.database_validator.validate(temp_database).is_valid:
                    raise ValueError("Copied database failed validation.")
                if target.database_path.exists():
                    previous_target.unlink(missing_ok=True)
                    os.replace(target.database_path, previous_target)
                else:
                    new_database_created = True
                os.replace(temp_database, target.database_path)
                database_copied = True

            final_database = self.database_validator.validate(
                target.database_path
            )
            if not final_database.is_valid:
                raise ValueError("Target database is not valid.")

            if request.copy_recorder_profiles:
                profiles_copied = self._copy_recorder_profiles(
                    source.data_root,
                    target.data_root,
                )
            if request.copy_output and source.output_root.exists():
                shutil.copytree(
                    source.output_root,
                    target.output_root,
                    dirs_exist_ok=True,
                )
                output_copied = True
            if request.copy_logs and source.logs_root.exists():
                shutil.copytree(
                    source.logs_root,
                    target.logs_root,
                    dirs_exist_ok=True,
                )
                logs_copied = True

            old_pointer = self.registry.read_storage_pointer()
            registry_write_attempted = True
            self.registry.write_storage_pointer(
                target.data_root,
                target.database_path,
            )
            registry_updated = True
            previous_target.unlink(missing_ok=True)
            logger.info("Data location relocation completed: %s", target.data_root)
        except Exception as exc:
            logger.exception("Data location relocation failed.")
            errors.append(f"Data location change failed: {exc}")
            temp_database.unlink(missing_ok=True)
            if previous_target.exists():
                target.database_path.unlink(missing_ok=True)
                os.replace(previous_target, target.database_path)
                database_copied = False
            elif new_database_created and not registry_updated:
                target.database_path.unlink(missing_ok=True)
                database_copied = False
            if registry_write_attempted and old_pointer is not None:
                try:
                    self.registry.write_storage_pointer(
                        old_pointer.data_root,
                        old_pointer.database_path,
                    )
                    registry_updated = False
                except Exception:
                    warnings.append(
                        "Unable to restore the previous Registry pointer."
                    )

        return DataLocationChangeResult(
            success=not errors,
            source_data_root=source.data_root,
            target_data_root=target.data_root,
            target_database_path=target.database_path,
            database_copied=database_copied,
            recorder_profiles_copied=profiles_copied,
            output_copied=output_copied,
            logs_copied=logs_copied,
            registry_updated=registry_updated,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    @staticmethod
    def _copy_recorder_profiles(
        source_root: Path,
        target_root: Path,
    ) -> int:
        source = resolve_storage_layout(source_root)
        if not source.recorder_profiles_root.exists():
            return 0
        copied = 0
        for profile in source.recorder_profiles_root.rglob("*.json"):
            relative = to_relative_profile_path(source_root, profile)
            validation = validate_profile_reference(source_root, relative)
            if validation.errors or not validation.json_object_valid:
                raise ValueError(
                    f"Recorder profile is invalid: {relative}"
                )
            destination = target_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(profile, destination)
            copied += 1
        return copied


def change_data_location(
    current_data_root: str | Path,
    target_data_root: str | Path,
    *,
    registry: StorageRegistryService,
    copy_database: bool = True,
    copy_recorder_profiles: bool = True,
    copy_output: bool = False,
    copy_logs: bool = False,
    overwrite_target_database: bool = False,
) -> DataLocationChangeResult:
    request = DataLocationChangeRequest(
        current_data_root=Path(current_data_root),
        target_data_root=Path(target_data_root),
        copy_database=copy_database,
        copy_recorder_profiles=copy_recorder_profiles,
        copy_output=copy_output,
        copy_logs=copy_logs,
        overwrite_target_database=overwrite_target_database,
    )
    return DataLocationManager(registry).change_data_location(request)
