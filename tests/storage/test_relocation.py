"""Controlled relocation with SQLite backup and pointer-last activation."""

from __future__ import annotations

import json
from pathlib import Path

from shared.database import BackupManager, DatabaseValidator
from shared.storage import (
    DataLocationChangeRequest,
    DataLocationManager,
    StorageBootstrapRequest,
    StorageBootstrapService,
    get_database_path,
)
from shared.storage.registry import (
    FakeRegistryBackend,
    StorageRegistryService,
)


def _profile(root: Path, name: str = "ho.json") -> Path:
    profile = root / "recorder_profiles" / "hris" / name
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        json.dumps({"profile": name}),
        encoding="utf-8",
    )
    return profile


def test_relocation_copies_database_and_updates_pointer(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    assert result.success
    assert result.database_copied
    assert DatabaseValidator().validate(
        get_database_path(target)
    ).is_valid
    assert fake_registry.read_storage_pointer().data_root == target


def test_relocation_uses_sqlite_backup_api(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    class SpyBackupManager:
        def __init__(self) -> None:
            self.calls = 0

        def create_backup(self, source, destination):
            self.calls += 1
            return BackupManager().create_backup(source, destination)

    spy = SpyBackupManager()
    result = DataLocationManager(
        fake_registry,
        backup_manager=spy,
    ).change_data_location(
        DataLocationChangeRequest(
            bootstrapped_root,
            tmp_path / "target",
        )
    )

    assert result.success
    assert spy.calls == 1


def test_relocation_copies_valid_recorder_profiles(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    _profile(bootstrapped_root, "ho_upload_profile.json")
    ignored = (
        bootstrapped_root
        / "recorder_profiles"
        / "hris"
        / "notes.txt"
    )
    ignored.write_text("ignore", encoding="utf-8")
    target = tmp_path / "target"

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    assert result.success
    assert result.recorder_profiles_copied == 1
    assert (
        target
        / "recorder_profiles"
        / "hris"
        / "ho_upload_profile.json"
    ).is_file()
    assert not (
        target / "recorder_profiles" / "hris" / "notes.txt"
    ).exists()


def test_source_is_never_deleted(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    source_database = get_database_path(bootstrapped_root)

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(
            bootstrapped_root,
            tmp_path / "target",
        )
    )

    assert result.success
    assert bootstrapped_root.is_dir()
    assert source_database.is_file()


def test_output_and_logs_are_not_copied_by_default(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    (bootstrapped_root / "output" / "large.txt").write_text(
        "output", encoding="utf-8"
    )
    (bootstrapped_root / "logs" / "process.log").write_text(
        "log", encoding="utf-8"
    )
    target = tmp_path / "target"

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    assert result.success
    assert not (target / "output" / "large.txt").exists()
    assert not (target / "logs" / "process.log").exists()


def test_output_and_logs_copy_only_when_explicit(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    (bootstrapped_root / "output" / "result.txt").write_text(
        "output", encoding="utf-8"
    )
    (bootstrapped_root / "logs" / "process.log").write_text(
        "log", encoding="utf-8"
    )
    target = tmp_path / "target"

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(
            bootstrapped_root,
            target,
            copy_output=True,
            copy_logs=True,
        )
    )

    assert result.success
    assert (target / "output" / "result.txt").is_file()
    assert (target / "logs" / "process.log").is_file()


def test_existing_target_database_requires_explicit_overwrite(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(
            target,
            "target-test",
            update_registry=False,
        )
    )
    fake_registry.write_storage_pointer(
        bootstrapped_root,
        get_database_path(bootstrapped_root),
    )

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    assert not result.success
    assert fake_registry.read_storage_pointer().data_root == bootstrapped_root


def test_target_validation_failure_keeps_old_pointer(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("blocked", encoding="utf-8")

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    assert not result.success
    assert fake_registry.read_storage_pointer().data_root == bootstrapped_root
    assert target.read_text(encoding="utf-8") == "blocked"


def test_registry_failure_rolls_back_new_target_database(
    bootstrapped_root: Path,
    fake_backend: FakeRegistryBackend,
    fake_registry: StorageRegistryService,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    fake_backend.available = False

    result = DataLocationManager(fake_registry).change_data_location(
        DataLocationChangeRequest(bootstrapped_root, target)
    )

    fake_backend.available = True
    assert not result.success
    assert not get_database_path(target).exists()
    assert fake_registry.read_storage_pointer().data_root == bootstrapped_root
