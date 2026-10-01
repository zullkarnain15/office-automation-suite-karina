"""Import a compatible database into the standard active Data Root."""

from __future__ import annotations

import shutil
from pathlib import Path

from shared.database.time_utils import current_timestamp
from shared.recovery.audit_service import RecoveryAuditService
from shared.recovery.backup_service import DatabaseBackupService
from shared.recovery.candidate_validator import CandidateValidator
from shared.recovery.constants import BackupReason
from shared.recovery.exceptions import ConfirmationRequiredError
from shared.recovery.models import ImportDatabaseRequest, ImportDatabaseResult
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


class ImportDatabaseService:
    def __init__(
        self,
        registry: StorageRegistryService | None = None,
        *,
        candidate_validator: CandidateValidator | None = None,
        backup_service: DatabaseBackupService | None = None,
        audit_service: RecoveryAuditService | None = None,
        staging_manager: StagingManager | None = None,
    ) -> None:
        self.registry = registry
        self.candidate_validator = candidate_validator or CandidateValidator()
        self.backup_service = backup_service or DatabaseBackupService()
        self.audit_service = audit_service or RecoveryAuditService()
        self.staging_manager = staging_manager or StagingManager()

    def import_database(
        self,
        request: ImportDatabaseRequest,
    ) -> ImportDatabaseResult:
        source = Path(request.source_database).expanduser()
        layout = resolve_storage_layout(request.active_data_root)
        staging: Path | None = None
        operation_id: str | None = None
        rollback: Path | None = None
        prebackup: Path | None = None
        rolled_back = False
        warnings: list[str] = []
        started = current_timestamp()
        old_hash = hash_if_readable(layout.database_path)
        try:
            if not request.confirm:
                raise ConfirmationRequiredError(
                    "Import requires explicit confirm=True."
                )
            validate_active_storage(layout.data_root)
            if source.resolve() == layout.database_path.resolve():
                raise ValueError(
                    "Source database is already the active database."
                )
            source_validation = self.candidate_validator.validate(source)
            if not source_validation.can_activate:
                raise ValueError(
                    "Import candidate is invalid: "
                    + "; ".join(source_validation.errors)
                )
            prebackup, backup_warnings = create_pre_operation_backup(
                layout.data_root,
                reason=BackupReason.BEFORE_IMPORT,
                operator=request.operator,
                force_without_prebackup=request.force_without_prebackup,
                service=self.backup_service,
            )
            warnings.extend(backup_warnings)
            operation_id, staging = self.staging_manager.create(layout.data_root)
            candidate = staging / "candidate.db"
            shutil.copy2(source, candidate)
            if not self.candidate_validator.validate(candidate).can_activate:
                raise ValueError("Staged import candidate failed validation.")
            rollback = staging / "active.rollback.db"
            self.staging_manager.activate(
                candidate,
                layout.database_path,
                rollback,
            )
            if not self.candidate_validator.validate(
                layout.database_path
            ).can_activate:
                raise RuntimeError("Imported active database failed validation.")
            new_hash = hash_if_readable(layout.database_path)
            record_recovery_operation(
                layout.database_path,
                operation="IMPORT_EXISTING_DATABASE",
                source_type="DATABASE",
                action_type="IMPORT_EXISTING_DATABASE",
                change_source="Migration",
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
            return ImportDatabaseResult(
                success=True,
                source_database=source,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                registry_updated=registry_updated,
                operation_id=operation_id,
                warnings=tuple(warnings),
            )
        except Exception as exc:
            if rollback is not None:
                rolled_back = self.staging_manager.rollback(
                    layout.database_path,
                    rollback,
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
            return ImportDatabaseResult(
                success=False,
                source_database=source,
                active_database=layout.database_path,
                pre_operation_backup=prebackup,
                rolled_back=rolled_back,
                operation_id=operation_id,
                warnings=tuple(warnings),
                errors=(f"Import failed: {exc}",),
            )
        finally:
            if staging is not None:
                self.staging_manager.cleanup(staging)

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
                operation="IMPORT_EXISTING_DATABASE",
                source_type="DATABASE",
                action_type="IMPORT_EXISTING_DATABASE",
                change_source="Migration",
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


def import_existing_database(
    request: ImportDatabaseRequest,
    *,
    registry: StorageRegistryService | None = None,
) -> ImportDatabaseResult:
    return ImportDatabaseService(registry).import_database(request)
