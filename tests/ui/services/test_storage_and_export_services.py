"""Read-only storage, explicit initialization, relocation defaults, and export."""

from __future__ import annotations

from pathlib import Path

from shared.database import SchemaManager
from shared.storage.constants import REGISTRY_KEY
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.services.configuration_ui_service import ConfigurationUIService
from ui.services.storage_ui_service import StorageUIService


def test_storage_status_is_read_only(tmp_path: Path) -> None:
    root = tmp_path / "not-created"
    backend = FakeRegistryBackend()
    service = StorageUIService(
        StorageRegistryService(backend),
        application_version="ui2",
    )
    status = service.resolve_status()
    assert not root.exists()
    assert backend.write_count == 0
    assert status.database_exists is False


def test_initialize_only_runs_when_explicit(tmp_path: Path) -> None:
    root = tmp_path / "data"
    backend = FakeRegistryBackend()
    service = StorageUIService(
        StorageRegistryService(backend),
        application_version="ui2",
    )
    assert not root.exists()
    result = service.initialize(root, write_registry=False)
    assert result.success
    assert root.is_dir()
    assert backend.write_count == 0


def test_registry_write_is_separate_option(tmp_path: Path) -> None:
    root = tmp_path / "data"
    backend = FakeRegistryBackend()
    service = StorageUIService(
        StorageRegistryService(backend),
        application_version="ui2",
    )
    result = service.initialize(root, write_registry=True)
    assert result.success and result.registry_updated
    assert REGISTRY_KEY in backend.values


def test_relocation_defaults_exclude_output_and_logs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = StorageUIService(
        StorageRegistryService(FakeRegistryBackend()),
        application_version="ui2",
    )
    captured = []
    monkeypatch.setattr(service, "relocate", captured.append)
    service.relocate_to(tmp_path / "source", tmp_path / "target")
    request = captured[0]
    assert request.copy_database
    assert request.copy_recorder_profiles
    assert not request.copy_output
    assert not request.copy_logs


def test_export_current_configuration_through_facade(
    tmp_path: Path,
) -> None:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "ui2")
    template = (
        Path(__file__).resolve().parents[3]
        / "config"
        / "templates"
        / "OAS-K_Configuration_Template.xlsx"
    )
    output = tmp_path / "export.xlsx"
    result = ConfigurationUIService(template).export(
        database, output, overwrite=False
    )
    assert output.is_file()
    assert result.validation.is_valid
