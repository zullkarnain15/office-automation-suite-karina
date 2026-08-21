from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import SCHEMA_VERSION
from shared.database.database_validator import DatabaseValidator
from shared.database.models import JobHistoryRecord
from shared.database.repositories import JobRepository
from shared.database.schema_manager import SchemaManager
from shared.database.time_utils import current_timestamp
from shared.storage.path_resolver import resolve_storage_layout
from shared.update import ApplicationUpdateService, UpdatePackageValidator
from shared.update.exceptions import (
    UpdateBackupError,
    UpdateBusyError,
    UpdateStagingError,
)
from shared.update.health_check import PostUpdateHealthCheck
from shared.update.models import UpdatePackageInfo
from shared.update.staging_service import UpdateStagingService


CURRENT_VERSION = "1.0.0"
TARGET_VERSION = "1.1.0"


def test_valid_package_accepted(tmp_path: Path) -> None:
    package = build_package(tmp_path)
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert result.valid
    assert result.info is not None
    assert result.info.manifest.version == TARGET_VERSION


def test_malformed_zip_rejected(tmp_path: Path) -> None:
    package = tmp_path / "OAS-K_Update_v1.1.0.zip"
    package.write_bytes(b"not a zip")
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("ZIP" in error for error in result.errors)


def test_missing_manifest_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, remove={"manifest.json"})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("manifest" in error for error in result.errors)


def test_wrong_application_id_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, manifest_updates={"application_id": "other"})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("application_id" in error for error in result.errors)


@pytest.mark.parametrize("version", ["1.0.0", "0.9.9"])
def test_same_version_and_downgrade_rejected(tmp_path: Path, version: str) -> None:
    package = build_package(tmp_path, manifest_updates={"version": version})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("lebih tinggi" in error for error in result.errors)


def test_unsupported_package_format_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, manifest_updates={"package_format": 99})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("package_format" in error for error in result.errors)


def test_migration_request_accepts_supported_schema_range(tmp_path: Path) -> None:
    package = build_package(
        tmp_path,
        manifest_updates={
            "database_schema_from": SCHEMA_VERSION - 1,
            "database_schema_to": SCHEMA_VERSION,
            "migration_required": True,
        },
    )
    result = UpdatePackageValidator(
        active_schema_version=SCHEMA_VERSION - 1
    ).validate(package, current_version=CURRENT_VERSION)
    assert result.valid


def test_prepare_update_accepts_schema2_database_and_creates_valid_backup(
    tmp_path: Path,
) -> None:
    data_root = initialized_data_root(tmp_path)
    layout = resolve_storage_layout(data_root)
    _downgrade_current_database_to_schema2(layout.database_path)
    package = build_package(
        tmp_path,
        manifest_updates={
            "database_schema_from": 2,
            "database_schema_to": 2,
            "migration_required": False,
        },
    )

    result = ApplicationUpdateService().prepare_update(
        package,
        current_version=CURRENT_VERSION,
        data_root=data_root,
    )

    assert result.status == "STAGED"
    assert result.backup_path.is_file()
    backup_validation = DatabaseValidator(expected_version=2).validate(
        result.backup_path
    )
    assert backup_validation.is_valid, backup_validation.errors


def test_schema3_release_prepares_backs_up_migrates_and_preserves_data(
    tmp_path: Path,
) -> None:
    data_root = _initialized_schema3_data_root(tmp_path)
    layout = resolve_storage_layout(data_root)
    package = build_package(
        tmp_path,
        manifest_updates={
            "version": "1.0.7",
            "minimum_current_version": "1.0.4",
            "database_schema_from": 3,
            "database_schema_to": 4,
            "migration_required": True,
        },
    )

    prepared = ApplicationUpdateService().prepare_update(
        package,
        current_version="1.0.4",
        data_root=data_root,
    )

    assert prepared.status == "STAGED"
    assert prepared.backup_path is not None
    backup_validation = DatabaseValidator(expected_version=3).validate(
        prepared.backup_path
    )
    assert backup_validation.is_valid, backup_validation.errors
    assert prepared.transaction_path is not None

    health = PostUpdateHealthCheck(application_version="1.0.7").run(
        prepared.transaction_path,
        create_ui_shell=False,
    )

    assert health.status == "SUCCESS"
    assert health.database_schema_version == 4
    with SQLiteConnectionFactory().connect(
        layout.database_path,
        read_only=True,
    ) as connection:
        marker = connection.execute(
            "SELECT output_root, updated_by FROM global_settings "
            "WHERE global_settings_id = 1"
        ).fetchone()
        settings = connection.execute(
            "SELECT saturday_missing_out_default, midnight_time_out_default "
            "FROM att_data_repair_settings WHERE att_data_repair_settings_id = 1"
        ).fetchone()
    assert tuple(marker) == (r"C:\ProductionData\Output", "Production v1.0.4")
    assert tuple(settings) == ("11:00", "23:59")


def test_database_schema_mismatch_rejected(tmp_path: Path) -> None:
    package = build_package(
        tmp_path,
        manifest_updates={"database_schema_to": SCHEMA_VERSION + 1},
    )
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("database_schema_from" in error for error in result.errors)


def test_missing_executable_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, remove={"application/OAS-K.exe"})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("OAS-K.exe" in error for error in result.errors)


def test_checksum_mismatch_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, checksum_overrides={"application/OAS-K.exe": "0" * 64})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("Checksum tidak cocok" in error for error in result.errors)


@pytest.mark.parametrize("entry", ["/absolute.txt", "C:/absolute.txt", "../escape.txt"])
def test_unsafe_paths_rejected(tmp_path: Path, entry: str) -> None:
    package = build_package(tmp_path, extra_files={entry: b"unsafe"})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("tidak aman" in error or "keluar" in error for error in result.errors)


@pytest.mark.parametrize("entry", ["database/OAS-K.db", "application/hidden.mdb", "logs/run.log"])
def test_prohibited_data_file_rejected(tmp_path: Path, entry: str) -> None:
    package = build_package(tmp_path, extra_files={entry: b"sensitive"})
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("data sensitif" in error for error in result.errors)


def test_oversized_package_rejected(tmp_path: Path) -> None:
    package = build_package(tmp_path, extra_files={"application/big.bin": b"x" * 128})
    validator = UpdatePackageValidator(max_total_uncompressed_size=64)
    result = validator.validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("Ukuran ekstraksi" in error for error in result.errors)


def test_duplicate_path_rejected(tmp_path: Path) -> None:
    package = tmp_path / "OAS-K_Update_v1.1.0.zip"
    manifest_bytes = json.dumps(default_manifest()).encode("utf-8")
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("application/", b"")
        archive.writestr("application/OAS-K.exe", b"one")
        archive.writestr("application/OAS-K.exe", b"two")
        checksums = {
            "manifest.json": hashlib.sha256(manifest_bytes).hexdigest(),
            "application/OAS-K.exe": hashlib.sha256(b"two").hexdigest(),
        }
        archive.writestr(
            "checksums.sha256",
            "\n".join(f"{digest}  {name}" for name, digest in sorted(checksums.items())),
        )
    result = UpdatePackageValidator().validate(package, current_version=CURRENT_VERSION)
    assert not result.valid
    assert any("Duplicate" in error for error in result.errors)


def test_backup_failure_prevents_staging(tmp_path: Path) -> None:
    data_root = initialized_data_root(tmp_path)
    package = build_package(tmp_path)
    staging = SpyStagingService()
    service = ApplicationUpdateService(
        backup_service=FailingBackupService(),
        staging_service=staging,
    )
    with pytest.raises(UpdateBackupError):
        service.prepare_update(package, current_version=CURRENT_VERSION, data_root=data_root)
    assert staging.called is False
    assert not (data_root / "update" / "staging").exists()


def test_active_job_prevents_prepare(tmp_path: Path) -> None:
    data_root = initialized_data_root(tmp_path)
    layout = resolve_storage_layout(data_root)
    package = build_package(tmp_path)
    with SQLiteConnectionFactory().connect(layout.database_path) as connection:
        JobRepository(connection).create_job(
            JobHistoryRecord(
                job_id="running",
                module_code="HRIS",
                feature_code="UPLOAD",
                workflow="HO",
                unified_status="RUNNING",
                output_path_used=str(layout.output_root),
                used_global_output=True,
                used_global_period=True,
                created_at=current_timestamp(),
                started_at=current_timestamp(),
            )
        )
    with pytest.raises(UpdateBusyError):
        ApplicationUpdateService().prepare_update(
            package,
            current_version=CURRENT_VERSION,
            data_root=data_root,
        )


def test_partial_staging_cleaned_on_failure(tmp_path: Path, monkeypatch) -> None:
    data_root = initialized_data_root(tmp_path)
    package = build_package(tmp_path)
    staging = UpdateStagingService()

    def explode(_package_path, _destination):
        raise UpdateStagingError("forced staging failure")

    monkeypatch.setattr(staging, "_extract", explode)
    service = ApplicationUpdateService(staging_service=staging)
    with pytest.raises(UpdateStagingError):
        service.prepare_update(package, current_version=CURRENT_VERSION, data_root=data_root)
    staging_root = data_root / "update" / "staging"
    assert not list(staging_root.glob(".v1.1.0.*"))


def test_pending_update_written_atomically_and_active_files_unchanged(tmp_path: Path) -> None:
    data_root = initialized_data_root(tmp_path)
    layout = resolve_storage_layout(data_root)
    package = build_package(tmp_path)
    database_before = sha256(layout.database_path)
    active_app = tmp_path / "active_app" / "OAS-K.exe"
    active_app.parent.mkdir()
    active_app.write_bytes(b"active executable")
    active_app_before = sha256(active_app)

    result = ApplicationUpdateService().prepare_update(
        package,
        current_version=CURRENT_VERSION,
        data_root=data_root,
    )

    assert result.status == "STAGED"
    assert result.staging_path == data_root / "update" / "staging" / "v1.1.0"
    assert (result.staging_path / "application" / "OAS-K.exe").is_file()
    pending = json.loads((data_root / "update" / "update_pending.json").read_text())
    assert pending["status"] == "STAGED"
    assert pending["target_version"] == TARGET_VERSION
    assert pending["backup_path"] == str(result.backup_path)
    assert not list((data_root / "update").glob(".*.tmp"))
    assert sha256(layout.database_path) == database_before
    assert sha256(active_app) == active_app_before


def default_manifest(**updates):
    value = {
        "package_format": 1,
        "application_id": "oas-k",
        "application_name": "Office Automation Suite - Karina",
        "version": TARGET_VERSION,
        "minimum_current_version": "1.0.0",
        "package_type": "application_only",
        "database_schema_from": SCHEMA_VERSION,
        "database_schema_to": SCHEMA_VERSION,
        "migration_required": False,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "entry_executable": "OAS-K.exe",
    }
    value.update(updates)
    return value


def build_package(
    tmp_path: Path,
    *,
    manifest_updates=None,
    remove=None,
    extra_files=None,
    checksum_overrides=None,
) -> Path:
    manifest = default_manifest(**(manifest_updates or {}))
    files = {
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
        "release_notes.txt": b"Release notes\n",
        "application/OAS-K.exe": b"new executable\n",
    }
    files.update(extra_files or {})
    for name in remove or set():
        files.pop(name, None)
    checksums = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    checksums.update(checksum_overrides or {})
    checksum_text = "\n".join(f"{digest}  {name}" for name, digest in sorted(checksums.items()))
    package = tmp_path / f"OAS-K_Update_v{manifest.get('version', TARGET_VERSION)}.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("application/", b"")
        for name in sorted(files):
            archive.writestr(name, files[name])
        if "checksums.sha256" not in (remove or set()):
            archive.writestr("checksums.sha256", checksum_text)
    return package


def initialized_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "data_root"
    layout = resolve_storage_layout(data_root)
    layout.database_root.mkdir(parents=True)
    layout.backup_root.mkdir(parents=True)
    SchemaManager().initialize_database(layout.database_path, "1.0.0")
    return data_root


def _initialized_schema3_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "schema3_data_root"
    layout = resolve_storage_layout(data_root)
    layout.database_root.mkdir(parents=True)
    layout.backup_root.mkdir(parents=True)
    manager = SchemaManager()
    with SQLiteConnectionFactory().connect(
        layout.database_path,
        create_parent=True,
    ) as connection:
        for statement in manager._sql_statements(
            manager.schema_file.read_text(encoding="utf-8")
        ):
            connection.execute(statement)
        for migration_name in ("v1_to_v2.sql", "v2_to_v3.sql"):
            migration = manager.migrations_path / migration_name
            for statement in manager._sql_statements(
                migration.read_text(encoding="utf-8")
            ):
                connection.execute(statement)
        connection.execute(
            """
            INSERT INTO database_metadata (
                metadata_id, database_uuid, schema_version,
                application_version, created_at, updated_at
            ) VALUES (1, 'production-v104', 3, '1.0.4', CURRENT_TIMESTAMP,
                      CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            """
            INSERT INTO global_settings (
                global_settings_id, output_root, period_start, period_end,
                updated_at, updated_by
            ) VALUES (1, ?, NULL, NULL, CURRENT_TIMESTAMP, 'Production v1.0.4')
            """,
            (r"C:\ProductionData\Output",),
        )
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    return data_root


def _downgrade_current_database_to_schema2(database_path: Path) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        connection.execute("DROP TABLE att_data_repair_settings")
        connection.execute(
            "UPDATE database_metadata SET schema_version = 2 WHERE metadata_id = 1"
        )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FailingBackupService:
    def backup(self, request):
        from shared.recovery.models import DatabaseBackupResult

        return DatabaseBackupResult(
            success=False,
            source_path=request.database_path,
            backup_path=None,
            errors=("forced backup failure",),
        )


class SpyStagingService(UpdateStagingService):
    def __init__(self) -> None:
        self.called = False

    def stage(self, package_info: UpdatePackageInfo, data_root: str | Path) -> Path:
        self.called = True
        return super().stage(package_info, data_root)
