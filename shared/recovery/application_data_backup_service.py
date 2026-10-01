"""Standard ZIP backup and validation for OAS-K application data."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from shared.database import BackupManager
from shared.database.models import BackupHistoryRecord
from shared.database.time_utils import current_timestamp
from shared.recovery.audit_service import (
    RecoveryAuditService,
    safe_identifier,
    sha256_file,
)
from shared.recovery.candidate_validator import CandidateValidator
from shared.recovery.constants import (
    APPLICATION_DATA_FORMAT_VERSION,
    BACKUP_APPLICATION_DATA_DIRECTORY,
    DATABASE_ARCHIVE_PATH,
    MANIFEST_ARCHIVE_PATH,
)
from shared.recovery.exceptions import ApplicationDataBackupError
from shared.recovery.manifest import manifest_from_json, manifest_to_json
from shared.recovery.models import (
    ApplicationDataBackupRequest,
    ApplicationDataBackupResult,
    BackupManifest,
)
from shared.recovery.staging_manager import StagingManager
from shared.storage.path_resolver import resolve_storage_layout


class ApplicationDataBackupService:
    def __init__(
        self,
        backup_manager: BackupManager | None = None,
        candidate_validator: CandidateValidator | None = None,
        audit_service: RecoveryAuditService | None = None,
        staging_manager: StagingManager | None = None,
    ) -> None:
        self.backup_manager = backup_manager or BackupManager()
        self.candidate_validator = candidate_validator or CandidateValidator()
        self.audit_service = audit_service or RecoveryAuditService()
        self.staging_manager = staging_manager or StagingManager()

    def backup(
        self,
        request: ApplicationDataBackupRequest,
    ) -> ApplicationDataBackupResult:
        layout = resolve_storage_layout(request.data_root)
        archive_root = (
            Path(request.backup_root).expanduser()
            / BACKUP_APPLICATION_DATA_DIRECTORY
        )
        staging: Path | None = None
        try:
            if not request.application_version.strip():
                raise ValueError("application_version must not be empty.")
            validation = self.candidate_validator.validate(layout.database_path)
            if not validation.can_activate:
                raise ApplicationDataBackupError(
                    "Active database is invalid: " + "; ".join(validation.errors)
                )
            _, staging = self.staging_manager.create(layout.data_root)
            snapshot = staging / "OAS-K.snapshot.db"
            snapshot_result = self.backup_manager.create_backup(
                layout.database_path,
                snapshot,
            )
            archive_root.mkdir(parents=True, exist_ok=True)
            archive = self._unique_archive_path(archive_root)
            included = [DATABASE_ARCHIVE_PATH]
            profiles = sorted(
                layout.hris_recorder_profiles_root.glob("*.json")
                if layout.hris_recorder_profiles_root.exists()
                else ()
            )
            for profile in profiles:
                self._validate_profile_safe(profile)
            included.extend(
                profile.relative_to(layout.data_root).as_posix()
                for profile in profiles
            )
            optional_roots: list[Path] = []
            if request.include_logs:
                optional_roots.append(layout.logs_root)
            if request.include_diagnostics:
                optional_roots.append(layout.diagnostics_root)
            optional_files: list[Path] = []
            for root in optional_roots:
                if root.exists():
                    optional_files.extend(
                        path
                        for path in root.rglob("*")
                        if path.is_file() and staging not in path.parents
                    )
            included.extend(
                path.relative_to(layout.data_root).as_posix()
                for path in optional_files
            )
            manifest = BackupManifest(
                format_version=APPLICATION_DATA_FORMAT_VERSION,
                application_version=request.application_version.strip(),
                schema_version=snapshot_result.schema_version,
                created_at=current_timestamp(),
                source_data_root=str(layout.data_root),
                database_relative_path=DATABASE_ARCHIVE_PATH,
                database_sha256=snapshot_result.sha256,
                included_paths=tuple([*included, MANIFEST_ARCHIVE_PATH]),
                excluded_paths=("output", "build", "dist", "temp", "cache"),
                recorder_profile_count=len(profiles),
            )
            with zipfile.ZipFile(
                archive,
                "x",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zip_handle:
                zip_handle.write(snapshot, DATABASE_ARCHIVE_PATH)
                for path in [*profiles, *optional_files]:
                    zip_handle.write(
                        path,
                        path.relative_to(layout.data_root).as_posix(),
                    )
                zip_handle.writestr(
                    MANIFEST_ARCHIVE_PATH,
                    manifest_to_json(manifest),
                )
            verify_root = staging / "verify"
            checked_manifest, _ = self.validate_archive(
                archive,
                extract_to=verify_root,
            )
            history_id = self.audit_service.record_backup(
                layout.database_path,
                BackupHistoryRecord(
                    action_type="BACKUP",
                    source_path="application-data",
                    backup_path=safe_identifier(archive),
                    database_hash=snapshot_result.sha256,
                    schema_version=snapshot_result.schema_version,
                    started_at=manifest.created_at,
                    finished_at=current_timestamp(),
                    status="SUCCESS",
                    validation_result="VALID",
                    operator=request.operator,
                    notes="format=standard-zip",
                ),
            )
            return ApplicationDataBackupResult(
                success=True,
                source_data_root=layout.data_root,
                backup_path=archive,
                manifest=checked_manifest,
                sha256=sha256_file(archive),
                history_id=history_id,
            )
        except Exception as exc:
            return ApplicationDataBackupResult(
                success=False,
                source_data_root=layout.data_root,
                backup_path=None,
                errors=(f"Application data backup failed: {exc}",),
            )
        finally:
            if staging is not None:
                self.staging_manager.cleanup(staging)

    def validate_archive(
        self,
        archive_path: str | Path,
        *,
        extract_to: Path | None = None,
    ) -> tuple[BackupManifest, Path | None]:
        archive = Path(archive_path).expanduser()
        if not zipfile.is_zipfile(archive):
            raise ApplicationDataBackupError("Source is not a readable ZIP archive.")
        with zipfile.ZipFile(archive, "r") as zip_handle:
            infos = zip_handle.infolist()
            names = {info.filename for info in infos}
            for info in infos:
                self._validate_entry(info)
            if MANIFEST_ARCHIVE_PATH not in names:
                raise ApplicationDataBackupError("Archive manifest is missing.")
            if DATABASE_ARCHIVE_PATH not in names:
                raise ApplicationDataBackupError("Archive database is missing.")
            try:
                manifest = manifest_from_json(
                    zip_handle.read(MANIFEST_ARCHIVE_PATH).decode("utf-8")
                )
            except (KeyError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
                raise ApplicationDataBackupError(
                    f"Archive manifest is invalid: {exc}"
                ) from exc
            if manifest.format_version != APPLICATION_DATA_FORMAT_VERSION:
                raise ApplicationDataBackupError(
                    "Unsupported application-data backup format."
                )
            if manifest.database_relative_path != DATABASE_ARCHIVE_PATH:
                raise ApplicationDataBackupError("Manifest database path is invalid.")
            if extract_to is None:
                return manifest, None
            extracted_database: Path | None = None
            for info in infos:
                destination = extract_to.joinpath(*PurePosixPath(info.filename).parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zip_handle.open(info) as source, destination.open("xb") as target:
                    shutil.copyfileobj(source, target)
                if info.filename == DATABASE_ARCHIVE_PATH:
                    extracted_database = destination
        if extracted_database is None:
            raise ApplicationDataBackupError("Archive database extraction failed.")
        if sha256_file(extracted_database) != manifest.database_sha256:
            raise ApplicationDataBackupError("Archive database hash does not match.")
        candidate = self.candidate_validator.validate(extracted_database)
        if not candidate.can_activate:
            raise ApplicationDataBackupError(
                "Archive database failed validation: "
                + "; ".join(candidate.errors)
            )
        return manifest, extracted_database

    @staticmethod
    def _validate_entry(info: zipfile.ZipInfo) -> None:
        raw = info.filename.replace("\\", "/")
        path = PurePosixPath(raw)
        if (
            not raw
            or raw.startswith("/")
            or path.is_absolute()
            or ".." in path.parts
            or (path.parts and ":" in path.parts[0])
        ):
            raise ApplicationDataBackupError(
                f"Unsafe archive entry rejected: {info.filename}"
            )
        mode = info.external_attr >> 16
        if mode and (mode & 0o170000) == 0o120000:
            raise ApplicationDataBackupError("Archive symlinks are not allowed.")

    @staticmethod
    def _unique_archive_path(root: Path) -> Path:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = root / f"OAS-K_Application_Data_{stamp}.zip"
        if not base.exists():
            return base
        for number in range(1, 10_000):
            candidate = root / f"OAS-K_Application_Data_{stamp}_{number:03d}.zip"
            if not candidate.exists():
                return candidate
        raise RuntimeError("Unable to allocate a unique archive filename.")

    @staticmethod
    def _validate_profile_safe(path: Path) -> None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApplicationDataBackupError(
                f"Recorder profile is not valid JSON: {path.name}"
            ) from exc
        if not isinstance(value, dict):
            raise ApplicationDataBackupError(
                f"Recorder profile must contain a JSON object: {path.name}"
            )

        sensitive = ("password", "secret", "token", "credential", "api_key")

        def contains_sensitive_key(item: object) -> bool:
            if isinstance(item, dict):
                return any(
                    any(token in str(key).lower() for token in sensitive)
                    or contains_sensitive_key(child)
                    for key, child in item.items()
                )
            if isinstance(item, list):
                return any(contains_sensitive_key(child) for child in item)
            return False

        if contains_sensitive_key(value):
            raise ApplicationDataBackupError(
                f"Recorder profile contains credential-like fields: {path.name}"
            )


def backup_application_data(
    data_root: str | Path,
    backup_root: str | Path,
    application_version: str,
    *,
    include_logs: bool = False,
    include_diagnostics: bool = False,
    operator: str | None = None,
) -> ApplicationDataBackupResult:
    return ApplicationDataBackupService().backup(
        ApplicationDataBackupRequest(
            data_root=Path(data_root),
            backup_root=Path(backup_root),
            application_version=application_version,
            include_logs=include_logs,
            include_diagnostics=include_diagnostics,
            operator=operator,
        )
    )
