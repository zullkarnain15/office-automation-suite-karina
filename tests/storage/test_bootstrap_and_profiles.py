"""Explicit bootstrap and recorder-profile storage tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from shared.database import (
    DatabaseValidator,
    SQLiteConnectionFactory,
)
from shared.storage import (
    RecorderProfileError,
    StorageBootstrapRequest,
    StorageBootstrapService,
    get_database_path,
    get_hris_recorder_profiles_root,
    initialize_data_root,
    resolve_profile_path,
    to_relative_profile_path,
    validate_existing_database_candidate,
    validate_profile_reference,
)
from shared.storage.registry import (
    FakeRegistryBackend,
    StorageRegistryService,
)


def test_initialize_data_root_creates_all_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"

    layout, created = initialize_data_root(root)

    assert created
    assert all(directory.is_dir() for directory in layout.directories)
    assert not layout.database_path.exists()


def test_bootstrap_creates_valid_database(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> None:
    root = tmp_path / "data"

    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(root, "db3-test")
    )

    assert result.success
    assert result.database_created
    assert result.registry_updated
    assert DatabaseValidator().validate(result.database_path).is_valid


def test_second_bootstrap_does_not_overwrite_database(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
) -> None:
    database = get_database_path(bootstrapped_root)
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(bootstrapped_root, "db3-test")
    )
    after = hashlib.sha256(database.read_bytes()).hexdigest()

    assert result.success
    assert not result.database_created
    assert after == before


def test_existing_invalid_database_is_not_overwritten(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> None:
    root = tmp_path / "invalid"
    database = get_database_path(root)
    database.parent.mkdir(parents=True)
    database.write_bytes(b"invalid database")

    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(root, "db3-test")
    )

    assert not result.success
    assert database.read_bytes() == b"invalid database"
    assert fake_registry.read_storage_pointer() is None


def test_registry_failure_keeps_bootstrap_usable(tmp_path: Path) -> None:
    registry = StorageRegistryService(
        FakeRegistryBackend(available=False)
    )

    result = StorageBootstrapService(registry).initialize_storage(
        StorageBootstrapRequest(tmp_path / "data", "db3-test")
    )

    assert result.success
    assert result.database_created
    assert not result.registry_updated
    assert result.warnings


def test_bootstrap_can_skip_registry_write(
    tmp_path: Path,
    fake_backend: FakeRegistryBackend,
    fake_registry: StorageRegistryService,
) -> None:
    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(
            tmp_path / "data",
            "db3-test",
            update_registry=False,
        )
    )

    assert result.success
    assert not result.registry_updated
    assert fake_backend.write_count == 0


def test_bootstrap_does_not_insert_global_settings(
    bootstrapped_root: Path,
) -> None:
    with SQLiteConnectionFactory().connect(
        get_database_path(bootstrapped_root),
        read_only=True,
    ) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM global_settings"
        ).fetchone()[0]

    assert count == 0


def test_no_json_pointer_is_created(bootstrapped_root: Path) -> None:
    forbidden = {
        "app_location.json",
        "storage_pointer.json",
        "database_path.json",
    }

    assert not {
        path.name
        for path in bootstrapped_root.rglob("*.json")
    } & forbidden


def test_hris_profile_root_is_official_path(tmp_path: Path) -> None:
    assert get_hris_recorder_profiles_root(tmp_path) == (
        tmp_path / "recorder_profiles" / "hris"
    )


def test_absolute_profile_converts_to_relative(tmp_path: Path) -> None:
    profile = (
        tmp_path
        / "recorder_profiles"
        / "hris"
        / "ho_upload_profile.json"
    )

    relative = to_relative_profile_path(tmp_path, profile)

    assert relative == Path(
        "recorder_profiles/hris/ho_upload_profile.json"
    )
    assert resolve_profile_path(tmp_path, relative) == profile.resolve()


def test_profile_outside_recorder_root_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(RecorderProfileError):
        to_relative_profile_path(
            tmp_path,
            tmp_path / "outside.json",
        )


def test_profile_path_traversal_is_rejected(tmp_path: Path) -> None:
    result = validate_profile_reference(
        tmp_path,
        Path("recorder_profiles/hris/../../secret.json"),
    )

    assert result.errors
    assert result.reference is None


def test_non_json_profile_is_rejected(tmp_path: Path) -> None:
    result = validate_profile_reference(
        tmp_path,
        Path("recorder_profiles/hris/profile.txt"),
    )

    assert result.errors


def test_missing_profile_returns_warning(tmp_path: Path) -> None:
    result = validate_profile_reference(
        tmp_path,
        Path("recorder_profiles/hris/future.json"),
    )

    assert not result.exists
    assert result.warnings
    assert not result.errors


def test_valid_json_object_profile_is_accepted(tmp_path: Path) -> None:
    profile = (
        tmp_path / "recorder_profiles" / "hris" / "valid.json"
    )
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps({"profile": "ho"}),
        encoding="utf-8",
    )

    result = validate_profile_reference(
        tmp_path,
        Path("recorder_profiles/hris/valid.json"),
    )

    assert result.exists
    assert result.readable
    assert result.json_object_valid
    assert not result.errors


@pytest.mark.parametrize(
    "content",
    ("not json", "[1, 2, 3]"),
)
def test_invalid_profile_json_is_rejected(
    tmp_path: Path,
    content: str,
) -> None:
    profile = (
        tmp_path / "recorder_profiles" / "hris" / "invalid.json"
    )
    profile.parent.mkdir(parents=True)
    profile.write_text(content, encoding="utf-8")

    result = validate_profile_reference(
        tmp_path,
        Path("recorder_profiles/hris/invalid.json"),
    )

    assert result.errors
    assert not result.json_object_valid


def test_existing_database_candidate_validator(
    bootstrapped_root: Path,
) -> None:
    result = validate_existing_database_candidate(
        get_database_path(bootstrapped_root)
    )

    assert result.is_valid


def test_incompatible_database_candidate_is_rejected(
    bootstrapped_root: Path,
) -> None:
    database = get_database_path(bootstrapped_root)
    with SQLiteConnectionFactory().connect(database) as connection:
        connection.execute(
            "UPDATE database_metadata SET schema_version = 99"
        )

    result = validate_existing_database_candidate(database)

    assert not result.is_valid
