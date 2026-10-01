"""Explicit staged reset to an empty schema-v1 database."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from shared.database import SchemaManager
from shared.database.time_utils import current_timestamp
from shared.recovery.audit_service import RecoveryAuditService
from shared.recovery.backup_service import DatabaseBackupService
from shared.recovery.candidate_validator import CandidateValidator
from shared.recovery.constants import BackupReason
from shared.recovery.exceptions import ConfirmationRequiredError
from shared.recovery.models import ResetDatabaseRequest, ResetDatabaseResult
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


class ResetService:
    def __init__(
        self,
        registry: StorageRegistryService | None = None,
        *,
        schema_manager: SchemaManager | None = None,
        candidate_validator: CandidateValidator | None = None,
        backup_service: DatabaseBackupService | None = None,
        audit_service: RecoveryAuditService | None = None,
        staging_manager: StagingManager | None = None,
    ) -> None:
        self.registry = registry
        self.schema_manager = schema_manager or SchemaManager()
        self.candidate_validator = candidate_validator or CandidateValidator()
        self.backup_service = backup_service or DatabaseBackupService()
        self.audit_service = audit_service or RecoveryAuditService()
        self.staging_manager = staging_manager or StagingManager()

    def reset(self, request: ResetDatabaseRequest) -> ResetDatabaseResult:
        layout = resolve_storage_layout(request.active_data_root)
        staging: Path | None = None
        operation_id: str | None = None
        rollback: Path | None = None
        rollback_profiles: Path | None = None
        profiles_removed = False
        prebackup: Path | None = None
        rolled_back = False
        warnings: list[str] = []
        started = current_timestamp()
        old_hash = hash_if_readable(layout.database_path)
        try:
            if not request.confirm:
                raise ConfirmationRequiredError(
                    "Reset to Default requires explicit confirm=True."
                )
            if not request.application_version.strip():
                raise ValueError("application_version must not be empty.")
            validate_active_storage(layout.data_root)
            prebackup, backup_warnings = create_pre_operation_backup(
                layout.data_root,
                reason=BackupReason.BEFORE_RESET,
                operator=request.operator,
                force_without_prebackup=request.force_without_prebackup,
                service=self.backup_service,
            )
            warnings.extend(backup_warnings)
            operation_id, staging = self.staging_manager.create(layout.data_root)
            candidate = staging / "OAS-K.default.db"
            self.schema_manager.initialize_database(
                candidate,
                request.application_version,
                create_parent=True,
            )
            if not self.candidate_validator.validate(candidate).can_activate:
                raise RuntimeError("Fresh schema-v1 candidate failed validation.")
            rollback = staging / "active.rollback.db"
            self.staging_manager.activate(
                candidate,
                layout.database_path,
                rollback,
            )
            if not self.candidate_validator.validate(
                layout.database_path
            ).can_activate:
                raise RuntimeError("Reset active database failed validation.")
            if (
                not request.preserve_recorder_profiles
                and layout.recorder_profiles_root.exists()
            ):
                rollback_profiles = staging / "profiles.rollback"
                os.replace(
                    layout.recorder_profiles_root,
                    rollback_profiles,
                )
                layout.recorder_profiles_root.mkdir(parents=True)
                profiles_removed = True
            new_hash = hash_if_readable(layout.database_path)
            record_recovery_operation(
                layout.database_path,
                operation="RESET_TO_DEFAULT",
                source_type="SCHEMA_V1",
                action_type="RESET_TO_DEFAULT",
                change_source="Reset Default",
                success=True,
                timestamp=started,
                operator=request.operator,
                identifier="schema-v1",
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
            registry_updated = False
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
            return ResetDatabaseResult(
                success=True,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                registry_updated=registry_updated,
                recorder_profiles_preserved=(
                    request.preserve_recorder_profiles
                ),
                operation_id=operation_id,
                warnings=tuple(warnings),
            )
        except Exception as exc:
            if rollback is not None:
                rolled_back = self.staging_manager.rollback(
                    layout.database_path,
                    rollback,
                )
            if profiles_removed:
                shutil.rmtree(
                    layout.recorder_profiles_root,
                    ignore_errors=True,
                )
                if (
                    rollback_profiles is not None
                    and rollback_profiles.exists()
                ):
                    os.replace(
                        rollback_profiles,
                        layout.recorder_profiles_root,
                    )
            self._record_failure(
                layout.database_path,
                started,
                request.operator,
                old_hash,
                prebackup,
                str(exc),
            )
            return ResetDatabaseResult(
                success=False,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                recorder_profiles_preserved=True,
                rolled_back=rolled_back,
                operation_id=operation_id,
                warnings=tuple(warnings),
                errors=(f"Reset to Default failed: {exc}",),
            )
        finally:
            if staging is not None:
                self.staging_manager.cleanup(staging)

    def _record_failure(
        self,
        active: Path,
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
                operation="RESET_TO_DEFAULT",
                source_type="SCHEMA_V1",
                action_type="RESET_TO_DEFAULT",
                change_source="Reset Default",
                success=False,
                timestamp=timestamp,
                operator=operator,
                identifier="schema-v1",
                old_hash=old_hash,
                new_hash=hash_if_readable(active),
                warnings=(warning,),
                backup_path=prebackup,
                audit_service=self.audit_service,
            )
        except Exception:
            pass


def reset_to_default(
    request: ResetDatabaseRequest,
    *,
    registry: StorageRegistryService | None = None,
) -> ResetDatabaseResult:
    return ResetService(registry).reset(request)
