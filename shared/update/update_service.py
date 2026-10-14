"""Application-only update preparation service for manual ZIP packages."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from config.app_config import PROJECT_ROOT
from shared.database.backup_manager import BackupManager
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import SCHEMA_VERSION
from shared.database.database_validator import DatabaseValidator
from shared.database.time_utils import current_timestamp
from shared.logger import get_logger
from shared.recovery.backup_service import DatabaseBackupService
from shared.recovery.constants import BackupReason
from shared.recovery.models import DatabaseBackupRequest
from shared.storage.path_resolver import resolve_storage_layout
from shared.update.exceptions import (
    UpdateBackupError,
    UpdateBusyError,
    UpdateValidationError,
)
from shared.update.models import PENDING_STATUS_STAGED, PreparedUpdateResult
from shared.update.package_validator import UpdatePackageValidator
from shared.update.path_safety import require_under
from shared.update.staging_service import UpdateStagingService
from shared.update.transaction_store import UpdateTransactionStore
from shared.update.updater_launcher import UpdaterLauncher

logger = get_logger(__name__)
PENDING_FILENAME = "update_pending.json"
ACTIVE_JOB_STATUSES = ("PENDING", "VALIDATING", "READY_FOR_UPLOAD", "RUNNING", "PAUSED")


class _PreUpdateBackupAudit:
    """Avoid active-database audit writes during application-only update prep."""

    @staticmethod
    def record_backup(_database_path: Path, _record) -> int:
        return 0


class ApplicationUpdateService:
    """Validate, back up, stage, and record a pending manual application update."""

    def __init__(
        self,
        *,
        validator: UpdatePackageValidator | None = None,
        staging_service: UpdateStagingService | None = None,
        backup_service: DatabaseBackupService | None = None,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.validator = validator or UpdatePackageValidator()
        self.staging_service = staging_service or UpdateStagingService()
        self._backup_service_provided = backup_service is not None
        self.backup_service = backup_service or DatabaseBackupService(
            audit_service=_PreUpdateBackupAudit()
        )
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def validate_package(
        self,
        package_path: str | Path,
        *,
        current_version: str,
        active_schema_version: int = SCHEMA_VERSION,
    ):
        validator = UpdatePackageValidator(
            active_schema_version=active_schema_version,
            max_file_count=self.validator.max_file_count,
            max_total_uncompressed_size=self.validator.max_total_uncompressed_size,
        )
        result = validator.validate(package_path, current_version=current_version)
        logger.info(
            "Update package validation: path=%s current=%s valid=%s errors=%s",
            package_path,
            current_version,
            result.valid,
            len(result.errors),
        )
        return result

    def prepare_update(
        self,
        package_path: str | Path,
        *,
        current_version: str,
        data_root: str | Path,
        application_root: str | Path | None = None,
        operator: str | None = None,
    ) -> PreparedUpdateResult:
        layout = resolve_storage_layout(data_root)
        app_root = self._resolve_application_root(application_root)
        active_schema_version = self._active_schema_version(layout.database_path)
        self._ensure_no_active_jobs(layout.database_path)
        validation = self.validate_package(
            package_path,
            current_version=current_version,
            active_schema_version=active_schema_version,
        )
        if not validation.valid or validation.info is None:
            raise UpdateValidationError("; ".join(validation.errors))

        logger.info(
            "Preparing update package: path=%s target=%s data_root=%s",
            package_path,
            validation.info.manifest.version,
            layout.data_root,
        )
        backup_service = self._backup_service_for_schema(active_schema_version)
        backup = backup_service.backup(
            DatabaseBackupRequest(
                layout.database_path,
                layout.backup_root,
                BackupReason.PRE_UPDATE,
                operator=operator,
            )
        )
        if not backup.success or backup.backup_path is None:
            logger.error("Pre-update backup failed: %s", backup.errors)
            raise UpdateBackupError("; ".join(backup.errors or ("Backup gagal.",)))
        logger.info("Pre-update backup completed: %s", backup.backup_path)

        staging_path = self.staging_service.stage(validation.info, layout.data_root)
        logger.info("Update package staged: %s", staging_path)
        prepared_at = current_timestamp()
        transaction = UpdateTransactionStore(layout.data_root).create(
            current_version=current_version,
            target_version=validation.info.manifest.version,
            package_path=Path(package_path),
            package_sha256=validation.info.package_sha256,
            staging_path=staging_path,
            application_root=app_root,
            database_backup_path=backup.backup_path,
            entry_executable=validation.info.manifest.entry_executable,
            source_process_id=os.getpid(),
        )
        pending_path = layout.data_root / "update" / PENDING_FILENAME
        payload = {
            "status": PENDING_STATUS_STAGED,
            "transaction_id": transaction.transaction_id,
            "current_version": current_version,
            "target_version": validation.info.manifest.version,
            "package_path": str(Path(package_path)),
            "staging_path": str(staging_path),
            "transaction_path": str(transaction.transaction_path),
            "backup_path": str(backup.backup_path),
            "prepared_at": prepared_at,
            "package_sha256": validation.info.package_sha256,
        }
        self._atomic_write_json(pending_path, payload)
        logger.info("Pending update recorded: %s", pending_path)
        return PreparedUpdateResult(
            status=PENDING_STATUS_STAGED,
            current_version=current_version,
            target_version=validation.info.manifest.version,
            package_path=Path(package_path),
            staging_path=staging_path,
            backup_path=backup.backup_path,
            prepared_at=prepared_at,
            package_sha256=validation.info.package_sha256,
            pending_path=pending_path,
            transaction_id=transaction.transaction_id,
            transaction_path=transaction.transaction_path,
            warnings=validation.warnings,
        )

    def _backup_service_for_schema(self, schema_version: int) -> DatabaseBackupService:
        if self._backup_service_provided:
            return self.backup_service
        return DatabaseBackupService(
            backup_manager=BackupManager(
                validator=DatabaseValidator(
                    self.connection_factory,
                    expected_version=schema_version,
                )
            ),
            audit_service=_PreUpdateBackupAudit(),
        )

    def _active_schema_version(self, database_path: Path) -> int:
        with self.connection_factory.connect(database_path, read_only=True) as connection:
            row = connection.execute(
                "SELECT schema_version FROM database_metadata WHERE metadata_id=1"
            ).fetchone()
        if row is None:
            raise UpdateValidationError("Database aktif tidak memiliki metadata schema.")
        return int(row[0])

    def _ensure_no_active_jobs(self, database_path: Path) -> None:
        placeholders = ",".join("?" for _ in ACTIVE_JOB_STATUSES)
        with self.connection_factory.connect(database_path, read_only=True) as connection:
            row = connection.execute(
                f"SELECT COUNT(*) FROM job_history WHERE unified_status IN ({placeholders})",
                ACTIVE_JOB_STATUSES,
            ).fetchone()
        if row is not None and int(row[0]) > 0:
            raise UpdateBusyError(
                "Update preparation ditolak karena masih ada job OAS-K aktif."
            )

    def load_pending_transaction(self, data_root: str | Path):
        pending_path = Path(data_root) / "update" / PENDING_FILENAME
        if not pending_path.is_file():
            return None
        payload = json.loads(pending_path.read_text(encoding="utf-8"))
        transaction_path = payload.get("transaction_path")
        if not transaction_path:
            return None
        return UpdateTransactionStore(data_root).load(transaction_path)

    def cancel_staged_update(self, data_root: str | Path):
        store = UpdateTransactionStore(data_root)
        transaction = self.load_pending_transaction(data_root)
        if transaction is None:
            raise UpdateValidationError("Tidak ada prepared update untuk dibatalkan.")
        if transaction.status != "STAGED":
            raise UpdateValidationError("Prepared update hanya bisa dibatalkan saat STAGED.")
        staging_path = require_under(
            transaction.staging_path,
            Path(data_root) / "update" / "staging",
            "Staging path di luar update directory.",
        )
        if staging_path.exists():
            shutil.rmtree(staging_path)
        updated = store.update_status(transaction, "CANCELLED")
        pending_path = Path(data_root) / "update" / PENDING_FILENAME
        pending_path.unlink(missing_ok=True)
        return updated

    def request_apply_update(
        self,
        data_root: str | Path,
        *,
        wait_pid: int | None = None,
        shutdown_timeout: int = 60,
        health_timeout: int = 90,
    ):
        layout = resolve_storage_layout(data_root)
        self._ensure_no_active_jobs(layout.database_path)
        transaction = self.load_pending_transaction(data_root)
        if transaction is None:
            raise UpdateValidationError("Tidak ada update STAGED.")
        if transaction.status != "STAGED":
            raise UpdateValidationError(f"Status update bukan STAGED: {transaction.status}")
        if not transaction.staged_application_path.joinpath(transaction.entry_executable).is_file():
            raise UpdateValidationError("Executable staged update tidak ditemukan.")
        if not os.access(transaction.application_root, os.W_OK):
            raise UpdateValidationError("Application Root tidak writable oleh user saat ini.")
        free = shutil.disk_usage(transaction.application_root).free
        staged_size = sum(
            path.stat().st_size
            for path in transaction.staged_application_path.rglob("*")
            if path.is_file()
        )
        if free < staged_size * 2:
            raise UpdateValidationError("Ruang disk tidak cukup untuk apply update.")
        return UpdaterLauncher(data_root).launch(
            transaction,
            wait_pid=wait_pid or os.getpid(),
            shutdown_timeout=shutdown_timeout,
            health_timeout=health_timeout,
        )

    @staticmethod
    def _resolve_application_root(value: str | Path | None) -> Path:
        if value is not None:
            return Path(value).expanduser().resolve()
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return PROJECT_ROOT.resolve()

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file_handle:
                json.dump(payload, file_handle, indent=2, sort_keys=True)
                file_handle.write("\n")
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
