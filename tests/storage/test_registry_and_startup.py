"""Fake Registry behavior and non-mutating startup resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.storage import (
    DataRootManager,
    StartupStorageStatus,
    get_database_path,
)
from shared.storage.constants import (
    REGISTRY_DATABASE_PATH_VALUE,
    REGISTRY_DATA_ROOT_VALUE,
    REGISTRY_KEY,
)
from shared.storage.exceptions import (
    RegistryAccessError,
    RegistryPointerMalformedError,
)
from shared.storage.registry import (
    FakeRegistryBackend,
    StorageRegistryService,
)


def test_fake_registry_read_write_clear(
    tmp_path: Path,
    fake_backend: FakeRegistryBackend,
    fake_registry: StorageRegistryService,
) -> None:
    root = tmp_path / "data"
    database = get_database_path(root)

    written = fake_registry.write_storage_pointer(root, database)
    assert fake_registry.storage_pointer_exists()
    assert fake_registry.read_storage_pointer() == written

    fake_registry.clear_storage_pointer()
    assert not fake_registry.storage_pointer_exists()
    assert fake_registry.read_storage_pointer() is None
    assert fake_backend.write_count == 1


def test_missing_registry_pointer_is_handled(
    fake_registry: StorageRegistryService,
) -> None:
    assert fake_registry.read_storage_pointer() is None
    assert not fake_registry.storage_pointer_exists()


def test_incomplete_registry_pointer_is_rejected(tmp_path: Path) -> None:
    backend = FakeRegistryBackend(
        initial={
            REGISTRY_KEY: {
                REGISTRY_DATA_ROOT_VALUE: str(tmp_path / "data"),
            }
        }
    )
    service = StorageRegistryService(backend)

    with pytest.raises(
        RegistryPointerMalformedError,
        match="incomplete",
    ):
        service.read_storage_pointer()


def test_mismatched_database_pointer_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "data"
    backend = FakeRegistryBackend(
        initial={
            REGISTRY_KEY: {
                REGISTRY_DATA_ROOT_VALUE: str(root),
                REGISTRY_DATABASE_PATH_VALUE: str(tmp_path / "other.db"),
            }
        }
    )

    with pytest.raises(
        RegistryPointerMalformedError,
        match="does not match",
    ):
        StorageRegistryService(backend).read_storage_pointer()


def test_non_string_registry_value_is_rejected(tmp_path: Path) -> None:
    backend = FakeRegistryBackend()
    backend.values[REGISTRY_KEY] = {
        REGISTRY_DATA_ROOT_VALUE: 123,  # type: ignore[dict-item]
        REGISTRY_DATABASE_PATH_VALUE: str(tmp_path / "OAS-K.db"),
    }

    with pytest.raises(RegistryPointerMalformedError):
        StorageRegistryService(backend).read_storage_pointer()


def test_registry_unavailable_raises() -> None:
    service = StorageRegistryService(
        FakeRegistryBackend(available=False)
    )

    with pytest.raises(RegistryAccessError):
        service.read_storage_pointer()


def test_partial_registry_write_restores_previous_pointer(
    tmp_path: Path,
) -> None:
    class FailOnceBackend(FakeRegistryBackend):
        fail_next = False

        def write_values(self, key, values):
            if self.fail_next:
                self.fail_next = False
                self.values.setdefault(key, {})[
                    REGISTRY_DATA_ROOT_VALUE
                ] = values[REGISTRY_DATA_ROOT_VALUE]
                raise RegistryAccessError("partial write")
            super().write_values(key, values)

    backend = FailOnceBackend()
    service = StorageRegistryService(backend)
    old_root = tmp_path / "old"
    service.write_storage_pointer(
        old_root,
        get_database_path(old_root),
    )
    backend.fail_next = True

    with pytest.raises(RegistryAccessError):
        service.write_storage_pointer(
            tmp_path / "new",
            get_database_path(tmp_path / "new"),
        )

    assert service.read_storage_pointer().data_root == old_root


def test_startup_ready(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
) -> None:
    resolution = DataRootManager(
        fake_registry,
        default_data_root=bootstrapped_root.parent / "unused",
    ).resolve_startup_storage()

    assert resolution.status is StartupStorageStatus.READY
    assert resolution.data_root == bootstrapped_root


def test_active_database_path_resolution(
    bootstrapped_root: Path,
    fake_registry: StorageRegistryService,
) -> None:
    manager = DataRootManager(fake_registry)

    assert manager.get_active_data_root() == bootstrapped_root
    assert manager.get_active_database_path() == get_database_path(
        bootstrapped_root
    )


def test_startup_initial_setup_required(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> None:
    default = tmp_path / "missing-default"

    resolution = DataRootManager(
        fake_registry,
        default_data_root=default,
    ).resolve_startup_storage()

    assert resolution.status is StartupStorageStatus.INITIAL_SETUP_REQUIRED
    assert not default.exists()


def test_startup_available_not_registered(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> None:
    from shared.database import SchemaManager

    root = tmp_path / "available"
    database = get_database_path(root)
    SchemaManager().initialize_database(
        database,
        "db3-test",
        create_parent=True,
    )

    resolution = DataRootManager(
        fake_registry,
        default_data_root=root,
    ).resolve_startup_storage()

    assert (
        resolution.status
        is StartupStorageStatus.AVAILABLE_NOT_REGISTERED
    )
    assert fake_registry.read_storage_pointer() is None


def test_startup_recovery_required_for_invalid_database(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> None:
    root = tmp_path / "invalid"
    database = get_database_path(root)
    database.parent.mkdir(parents=True)
    database.write_bytes(b"not sqlite")
    fake_registry.write_storage_pointer(root, database)

    resolution = DataRootManager(
        fake_registry,
        default_data_root=tmp_path / "unused",
    ).resolve_startup_storage()

    assert resolution.status is StartupStorageStatus.RECOVERY_REQUIRED
    assert database.read_bytes() == b"not sqlite"


def test_startup_registry_unavailable_does_not_crash(
    tmp_path: Path,
) -> None:
    manager = DataRootManager(
        StorageRegistryService(
            FakeRegistryBackend(available=False)
        ),
        default_data_root=tmp_path / "unused",
    )

    resolution = manager.resolve_startup_storage()

    assert resolution.status is StartupStorageStatus.REGISTRY_UNAVAILABLE


def test_explicit_session_root_when_registry_unavailable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "explicit"
    root.mkdir()
    manager = DataRootManager(
        StorageRegistryService(
            FakeRegistryBackend(available=False)
        )
    )

    layout = manager.use_explicit_data_root(root)
    resolution = manager.resolve_startup_storage()

    assert layout.data_root == root
    assert manager.get_active_data_root() == root
    assert resolution.data_root == root


def test_import_does_not_touch_fake_registry(
    fake_backend: FakeRegistryBackend,
) -> None:
    assert fake_backend.read_count == 0
    assert fake_backend.write_count == 0
    assert fake_backend.delete_count == 0
