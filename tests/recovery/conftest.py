"""Isolated DB4 fixtures; no production Registry or default Data Root."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SchemaManager, SQLiteConnectionFactory
from shared.storage import StorageBootstrapRequest, StorageBootstrapService
from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService


@pytest.fixture
def fake_backend() -> FakeRegistryBackend:
    return FakeRegistryBackend()


@pytest.fixture
def fake_registry(
    fake_backend: FakeRegistryBackend,
) -> StorageRegistryService:
    return StorageRegistryService(fake_backend)


@pytest.fixture
def data_root(
    tmp_path: Path,
    fake_registry: StorageRegistryService,
) -> Path:
    root = tmp_path / "active-data"
    result = StorageBootstrapService(fake_registry).initialize_storage(
        StorageBootstrapRequest(root, "db4-active", update_registry=False)
    )
    assert result.success, result.errors
    return root


@pytest.fixture
def candidate_database(tmp_path: Path) -> Path:
    path = tmp_path / "candidate-source.db"
    SchemaManager().initialize_database(path, "db4-candidate")
    return path


@pytest.fixture
def factory() -> SQLiteConnectionFactory:
    return SQLiteConnectionFactory()


def application_version(path: Path) -> str:
    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        row = connection.execute(
            "SELECT application_version FROM database_metadata WHERE metadata_id=1"
        ).fetchone()
    assert row is not None
    return str(row[0])


def active_database(data_root: Path) -> Path:
    return resolve_storage_layout(data_root).database_path
