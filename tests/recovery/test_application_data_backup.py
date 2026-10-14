"""Standard ZIP application-data backup tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from shared.recovery import (
    ApplicationDataBackupRequest,
    ApplicationDataBackupService,
)
from shared.recovery.audit_service import sha256_file
from shared.recovery.constants import DATABASE_ARCHIVE_PATH, MANIFEST_ARCHIVE_PATH
from shared.recovery.exceptions import ApplicationDataBackupError
from shared.storage.path_resolver import resolve_storage_layout


def _backup(data_root: Path):
    layout = resolve_storage_layout(data_root)
    return ApplicationDataBackupService().backup(
        ApplicationDataBackupRequest(
            data_root,
            layout.backup_root,
            "db4-test",
        )
    )


def test_app_data_zip_succeeds(data_root: Path) -> None:
    result = _backup(data_root)
    assert result.success
    assert result.backup_path is not None
    assert zipfile.is_zipfile(result.backup_path)


def test_manifest_valid(data_root: Path) -> None:
    result = _backup(data_root)
    assert result.manifest is not None
    assert result.manifest.format_version == 1
    assert result.manifest.database_relative_path == DATABASE_ARCHIVE_PATH


def test_database_hash_matches(data_root: Path, tmp_path: Path) -> None:
    result = _backup(data_root)
    assert result.backup_path is not None and result.manifest is not None
    with zipfile.ZipFile(result.backup_path) as archive:
        archive.extract(DATABASE_ARCHIVE_PATH, tmp_path)
    assert (
        sha256_file(tmp_path / DATABASE_ARCHIVE_PATH)
        == result.manifest.database_sha256
    )


def test_recorder_profiles_included(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    profile = layout.hris_recorder_profiles_root / "workflow.json"
    profile.write_text('{"steps": []}', encoding="utf-8")
    result = _backup(data_root)
    assert result.backup_path is not None
    with zipfile.ZipFile(result.backup_path) as archive:
        assert "recorder_profiles/hris/workflow.json" in archive.namelist()
    assert result.manifest is not None
    assert result.manifest.recorder_profile_count == 1


def test_output_excluded_by_default(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    (layout.output_root / "report.xlsx").write_bytes(b"result")
    result = _backup(data_root)
    assert result.backup_path is not None
    with zipfile.ZipFile(result.backup_path) as archive:
        assert all(not name.startswith("output/") for name in archive.namelist())


def test_profile_with_credentials_is_rejected(data_root: Path) -> None:
    layout = resolve_storage_layout(data_root)
    profile = layout.hris_recorder_profiles_root / "unsafe.json"
    profile.write_text('{"password": "do-not-back-up"}', encoding="utf-8")
    result = _backup(data_root)
    assert not result.success
    assert "credential-like" in result.errors[0]


def test_manifest_and_database_present(data_root: Path) -> None:
    result = _backup(data_root)
    assert result.backup_path is not None
    with zipfile.ZipFile(result.backup_path) as archive:
        assert {MANIFEST_ARCHIVE_PATH, DATABASE_ARCHIVE_PATH} <= set(
            archive.namelist()
        )


def test_path_traversal_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.db", b"bad")
        handle.writestr(MANIFEST_ARCHIVE_PATH, "{}")
        handle.writestr(DATABASE_ARCHIVE_PATH, b"bad")
    with pytest.raises(ApplicationDataBackupError, match="Unsafe"):
        ApplicationDataBackupService().validate_archive(archive)


def test_absolute_archive_entry_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "absolute.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("/outside", b"bad")
    with pytest.raises(ApplicationDataBackupError, match="Unsafe"):
        ApplicationDataBackupService().validate_archive(archive)


def test_invalid_zip_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.zip"
    invalid.write_bytes(b"not zip")
    with pytest.raises(ApplicationDataBackupError, match="not a readable"):
        ApplicationDataBackupService().validate_archive(invalid)


def test_bad_database_hash_rejected(data_root: Path, tmp_path: Path) -> None:
    result = _backup(data_root)
    assert result.backup_path is not None
    altered = tmp_path / "altered.zip"
    with zipfile.ZipFile(result.backup_path) as source, zipfile.ZipFile(
        altered, "w"
    ) as target:
        for info in source.infolist():
            payload = source.read(info)
            if info.filename == MANIFEST_ARCHIVE_PATH:
                manifest = json.loads(payload)
                manifest["database_sha256"] = "0" * 64
                payload = json.dumps(manifest).encode()
            target.writestr(info, payload)
    with pytest.raises(ApplicationDataBackupError, match="hash"):
        ApplicationDataBackupService().validate_archive(
            altered,
            extract_to=tmp_path / "extract",
        )
