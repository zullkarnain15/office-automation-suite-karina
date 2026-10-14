"""Explicit restore from a database file or official app-data ZIP."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from shared.database.time_utils import current_timestamp
from shared.recovery.application_data_backup_service import (
    ApplicationDataBackupService,
)
from shared.recovery.audit_service import RecoveryAuditService
from shared.recovery.backup_service import DatabaseBackupService
from shared.recovery.candidate_validator import CandidateValidator
from shared.recovery.constants import BackupReason
from shared.recovery.exceptions import ConfirmationRequiredError
from shared.recovery.models import RestoreRequest, RestoreResult
from shared.recovery.operation_support import (
    create_pre_operation_backup,
    hash_if_readable,
    record_recovery_operation,
    validate_active_storage,
)
from shared.recovery.staging_manager import StagingManager
from shared.storage.exceptions import RegistryAccessError
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry.windows_registry import StorageRegistryService


class RestoreService:
    def __init__(
        self,
        registry: StorageRegistryService | None = None,
        *,
        candidate_validator: CandidateValidator | None = None,
        backup_service: DatabaseBackupService | None = None,
        app_backup_service: ApplicationDataBackupService | None = None,
        audit_service: RecoveryAuditService | None = None,
        staging_manager: StagingManager | None = None,
    ) -> None:
        self.registry = registry
        self.candidate_validator = candidate_validator or CandidateValidator()
        self.backup_service = backup_service or DatabaseBackupService()
        self.app_backup_service = (
            app_backup_service or ApplicationDataBackupService()
        )
        self.audit_service = audit_service or RecoveryAuditService()
        self.staging_manager = staging_manager or StagingManager()

    def restore(self, request: RestoreRequest) -> RestoreResult:
        source = Path(request.source_backup).expanduser()
        layout = resolve_storage_layout(request.active_data_root)
        staging: Path | None = None
        operation_id: str | None = None
        prebackup: Path | None = None
        rollback_database: Path | None = None
        rollback_profiles: Path | None = None
        profiles_swapped = False
        rolled_back = False
        registry_updated = False
        profiles_restored = 0
        warnings: list[str] = []
        started = current_timestamp()
        old_hash = hash_if_readable(layout.database_path)
        try:
            if not request.confirm:
                raise ConfirmationRequiredError(
                    "Restore requires explicit confirm=True."
                )
            if not source.is_file():
                raise FileNotFoundError(f"Backup source does not exist: {source}")
            validate_active_storage(layout.data_root)
            operation_id, staging = self.staging_manager.create(layout.data_root)
            extracted_root = staging / "source"
            if zipfile.is_zipfile(source):
                _, candidate = self.app_backup_service.validate_archive(
                    source,
                    extract_to=extracted_root,
                )
                if candidate is None:
                    raise RuntimeError("Archive database was not extracted.")
                source_type = "APPLICATION_DATA_BACKUP"
            else:
                candidate = staging / "candidate.db"
                shutil.copy2(source, candidate)
                source_type = "DATABASE_BACKUP"
            validation = self.candidate_validator.validate(candidate)
            if not validation.can_activate:
                raise ValueError(
                    "Restore candidate is invalid: "
                    + "; ".join(validation.errors)
                )
            prebackup, backup_warnings = create_pre_operation_backup(
                layout.data_root,
                reason=BackupReason.BEFORE_RESTORE,
                operator=request.operator,
                force_without_prebackup=request.force_without_prebackup,
                service=self.backup_service,
            )
            warnings.extend(backup_warnings)
            rollback_database = staging / "active.rollback.db"
            self.staging_manager.activate(
                candidate,
                layout.database_path,
                rollback_database,
            )
            active_validation = self.candidate_validator.validate(
                layout.database_path
            )
            if not active_validation.can_activate:
                raise RuntimeError("Activated database failed final validation.")
            if (
                source_type == "APPLICATION_DATA_BACKUP"
                and request.restore_recorder_profiles
            ):
                extracted_profiles = extracted_root / "recorder_profiles"
                if extracted_profiles.exists():
                    profiles_restored = self._profile_count(extracted_profiles)
                    profiles_swapped, rollback_profiles = self._activate_profiles(
                        extracted_profiles,
                        layout.recorder_profiles_root,
                        staging,
                    )
            new_hash = hash_if_readable(layout.database_path)
            record_recovery_operation(
                layout.database_path,
                operation="RESTORE_FROM_BACKUP",
                source_type=source_type,
                action_type="RESTORE_FROM_BACKUP",
                change_source="Restore",
                success=True,
                timestamp=started,
                operator=request.operator,
                identifier=source.name,
                old_hash=old_hash,
                new_hash=new_hash,
                warnings=tuple(warnings),
                backup_path=prebackup,
                audit_service=self.audit_service,
            )
            if not self.candidate_validator.validate(
                layout.database_path
            ).can_activate:
                raise RuntimeError(
                    "Active database failed validation after recovery audit."
                )
            if request.update_registry:
                if self.registry is None:
                    raise RegistryAccessError(
                        "Registry update was requested but no backend was supplied."
                    )
                self.registry.write_storage_pointer(
                    layout.data_root,
                    layout.database_path,
                )
                registry_updated = True
            return RestoreResult(
                success=True,
                source_backup=source,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                recorder_profiles_restored=profiles_restored,
                registry_updated=registry_updated,
                operation_id=operation_id,
                warnings=tuple(warnings),
            )
        except Exception as exc:
            if rollback_database is not None:
                rolled_back = self.staging_manager.rollback(
                    layout.database_path,
                    rollback_database,
                )
            if profiles_swapped:
                shutil.rmtree(layout.recorder_profiles_root, ignore_errors=True)
                if rollback_profiles is not None and rollback_profiles.exists():
                    os.replace(
                        rollback_profiles,
                        layout.recorder_profiles_root,
                    )
            self._record_failure(
                layout.database_path,
                source.name,
                started,
                request.operator,
                old_hash,
                prebackup,
                str(exc),
            )
            return RestoreResult(
                success=False,
                source_backup=source,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                registry_updated=False,
                rolled_back=rolled_back,
                operation_id=operation_id,
                warnings=tuple(warnings),
                errors=(f"Restore failed: {exc}",),
            )
        finally:
            if staging is not None:
                self.staging_manager.cleanup(staging)

    @staticmethod
    def _activate_profiles(
        extracted: Path,
        active: Path,
        staging: Path,
    ) -> tuple[bool, Path | None]:
        merged = staging / "profiles.merged"
        if active.exists():
            shutil.copytree(active, merged)
        else:
            merged.mkdir()
        shutil.copytree(extracted, merged, dirs_exist_ok=True)
        rollback = staging / "profiles.rollback"
        if active.exists():
            os.replace(active, rollback)
        try:
            os.replace(merged, active)
        except Exception:
            if rollback.exists():
                os.replace(rollback, active)
            raise
        return True, rollback if rollback.exists() else None

    @staticmethod
    def _profile_count(root: Path) -> int:
        return sum(1 for _ in root.rglob("*.json")) if root.exists() else 0

    def _record_failure(
        self,
        active: Path,
        identifier: str,
        timestamp: str,
        operator: str | None,
        old_hash: str | None,
        prebackup: Path | None,
        warning: str,
    ) -> None:
        if not self.candidate_validator.validate(active).can_activate:
            return
        try:
            record_recovery_operation(
                active,
                operation="RESTORE_FROM_BACKUP",
                source_type="BACKUP",
                action_type="RESTORE_FROM_BACKUP",
                change_source="Restore",
                success=False,
                timestamp=timestamp,
                operator=operator,
                identifier=identifier,
                old_hash=old_hash,
                new_hash=hash_if_readable(active),
                warnings=(warning,),
                backup_path=prebackup,
                audit_service=self.audit_service,
            )
        except Exception:
            pass


def restore_from_backup(
    request: RestoreRequest,
    *,
    registry: StorageRegistryService | None = None,
) -> RestoreResult:
    return RestoreService(registry).restore(request)
