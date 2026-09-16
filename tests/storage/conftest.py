"""Isolated fake-Registry and temporary storage fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.storage import (
    StorageBootstrapRequest,
    StorageBootstrapService,
)
from shared.storage.registry import (
    FakeRegistryBackend,
    StorageRegistryService,
)


@pytest.fixture
def fake_backend() -> FakeRegistryBackend:
    return FakeRegistryBackend()


@pytest.fixture
def fake_registry(
    fake_backend: FakeRegistryBackend,
) -> StorageRegistryService:
    return StorageRegistryService(fake_backend)


@pytest.fixture
def bootstrapped_root(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> Path:
    root = tmp_path / "source-data"
    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(
            data_root=root,
            application_version="db3-test",
        )
    )
    assert result.success, result.errors
    return root
