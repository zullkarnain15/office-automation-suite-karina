"""Configuration and recorder-profile service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.storage import StorageBootstrapRequest, StorageBootstrapService
from shared.storage.registry import FakeRegistryBackend, StorageRegistryService
from ui.services.configuration_ui_service import ConfigurationUIService
from ui.services.recorder_profile_ui_service import RecorderProfileUIService


def test_template_copy_does_not_change_source(tmp_path: Path) -> None:
    source = tmp_path / "template.xlsx"
    source.write_bytes(b"template")
    target = tmp_path / "copy.xlsx"
    service = ConfigurationUIService(source)
    before = source.read_bytes()
    assert service.save_template_copy(target, overwrite=False) == target
    assert source.read_bytes() == before
    assert target.read_bytes() == before


def test_template_copy_requires_overwrite_confirmation(tmp_path: Path) -> None:
    source = tmp_path / "template.xlsx"
    target = tmp_path / "copy.xlsx"
    source.write_bytes(b"new")
    target.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        ConfigurationUIService(source).save_template_copy(
            target, overwrite=False
        )


def test_preview_delegates_without_commit(tmp_path: Path) -> None:
    calls: list[str] = []

    class FakeImporter:
        def preview(self, database, sources, global_resolution=None):
            calls.append("preview")
            return "preview-result"

        def commit(self, database, request):
            calls.append("commit")

    service = ConfigurationUIService(tmp_path / "template", FakeImporter())
    assert service.preview(tmp_path / "db", (tmp_path / "book.xlsx",)) == (
        "preview-result"
    )
    assert calls == ["preview"]


@pytest.fixture
def profile_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    registry = StorageRegistryService(FakeRegistryBackend())
    result = StorageBootstrapService(registry).initialize_storage(
        StorageBootstrapRequest(
            root, "ui2-test", update_registry=False
        )
    )
    assert result.success
    return root


def test_valid_json_profile_import_and_listing(
    profile_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "profile.json"
    source.write_text('{"steps": []}', encoding="utf-8")
    service = RecorderProfileUIService()
    relative = service.import_profile(
        source, profile_root, overwrite=False
    )
    values = service.list_profiles(profile_root)
    assert not relative.is_absolute()
    assert len(values) == 1 and values[0].valid


def test_invalid_json_profile_rejected(
    profile_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.json"
    source.write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="valid"):
        RecorderProfileUIService().import_profile(
            source, profile_root, overwrite=False
        )


def test_non_json_profile_rejected(
    profile_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "profile.txt"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        RecorderProfileUIService().import_profile(
            source, profile_root, overwrite=False
        )


def test_duplicate_profile_requires_overwrite(
    profile_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "profile.json"
    source.write_text("{}", encoding="utf-8")
    service = RecorderProfileUIService()
    service.import_profile(source, profile_root, overwrite=False)
    with pytest.raises(FileExistsError):
        service.import_profile(source, profile_root, overwrite=False)


def test_absolute_reference_rejected(profile_root: Path) -> None:
    result = RecorderProfileUIService().validate(
        profile_root, Path("C:/outside.json")
    )
    assert result.errors


def test_path_traversal_rejected(profile_root: Path) -> None:
    result = RecorderProfileUIService().validate(
        profile_root, Path("../outside.json")
    )
    assert result.errors


def test_remove_reference_does_not_delete_file(
    profile_root: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "profile.json"
    source.write_text("{}", encoding="utf-8")
    service = RecorderProfileUIService()
    relative = service.import_profile(source, profile_root, overwrite=False)
    assert service.remove_reference(relative) == relative
    assert (profile_root / relative).is_file()
