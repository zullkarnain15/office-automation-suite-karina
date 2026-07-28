"""Path layout and read-only validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.storage import (
    DEFAULT_DATA_ROOT,
    get_backup_root,
    get_database_path,
    get_diagnostics_root,
    get_hris_recorder_profiles_root,
    get_logs_root,
    get_output_root,
    get_recorder_profiles_root,
    resolve_storage_layout,
    suggested_fallback_data_root,
    validate_data_root,
)
from shared.storage import storage_validator


def test_default_data_root() -> None:
    assert str(DEFAULT_DATA_ROOT).replace("/", "\\") == r"D:\OAS-K\Data"


def test_path_resolver_returns_official_layout(tmp_path: Path) -> None:
    root = tmp_path / "Data"
    layout = resolve_storage_layout(root)

    assert get_database_path(root) == root / "database" / "OAS-K.db"
    assert get_backup_root(root) == root / "backup"
    assert get_output_root(root) == root / "output"
    assert get_logs_root(root) == root / "logs"
    assert get_diagnostics_root(root) == root / "diagnostics"
    assert get_recorder_profiles_root(root) == root / "recorder_profiles"
    assert get_hris_recorder_profiles_root(root) == (
        root / "recorder_profiles" / "hris"
    )
    assert len(layout.directories) == 8


def test_suggested_fallback_is_not_created(tmp_path: Path) -> None:
    suggestion = suggested_fallback_data_root(tmp_path)

    assert suggestion == tmp_path / "Documents" / "OAS-K" / "Data"
    assert not suggestion.exists()


def test_validate_missing_writable_temp_root(tmp_path: Path) -> None:
    root = tmp_path / "new-data-root"
    result = validate_data_root(root)

    assert not result.exists
    assert result.drive_available
    assert result.writable
    assert result.is_local
    assert result.can_initialize
    assert not root.exists()


def test_validate_existing_writable_root(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()

    result = validate_data_root(root)

    assert result.exists
    assert result.writable
    assert not result.database_exists


def test_missing_drive_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage_validator,
        "_drive_available",
        lambda _path: False,
    )

    result = validate_data_root(tmp_path / "data")

    assert not result.drive_available
    assert not result.can_initialize


def test_non_writable_parent_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage_validator,
        "_nearest_existing_parent_writable",
        lambda _path: False,
    )

    result = validate_data_root(tmp_path / "data")

    assert not result.writable
    assert any("writable" in error for error in result.errors)


def test_file_path_is_not_a_data_root(tmp_path: Path) -> None:
    candidate = tmp_path / "file"
    candidate.write_text("not a directory", encoding="utf-8")

    result = validate_data_root(candidate)

    assert not result.writable
    assert any("file" in error for error in result.errors)


def test_unc_network_path_is_rejected() -> None:
    result = validate_data_root(Path(r"\\server\share\OAS-K\Data"))

    assert not result.is_local
    assert not result.can_initialize


def test_missing_standard_directories_are_reported(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()

    result = validate_data_root(root)

    assert result.missing_directories
    assert root / "database" in result.missing_directories
