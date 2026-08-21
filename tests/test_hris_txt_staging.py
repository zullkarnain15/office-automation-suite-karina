from pathlib import Path

import pytest

from shared.hris_txt_staging import stage_hris_txt_files


@pytest.mark.parametrize(
    ("workflow", "folder_name"),
    (("HO", "HO"), ("BRANCH", "Branch")),
)
def test_stage_txt_copies_only_file_into_workflow_queue(
    tmp_path: Path,
    workflow: str,
    folder_name: str,
) -> None:
    source_folder = tmp_path / "module" / "job" / "TXT"
    source_folder.mkdir(parents=True)
    source = source_folder / "attendance.txt"
    source.write_text("original", encoding="utf-8")

    result = stage_hris_txt_files((source,), tmp_path / "output", workflow)

    destination = tmp_path / "output" / "HRIS" / folder_name / source.name
    assert result[0].status == "COPIED"
    assert result[0].destination_path == destination
    assert destination.read_text(encoding="utf-8") == "original"
    assert source.read_text(encoding="utf-8") == "original"
    assert not (destination.parent / "TXT").exists()


def test_stage_txt_skips_identical_duplicate(tmp_path: Path) -> None:
    source = tmp_path / "source" / "same.txt"
    source.parent.mkdir()
    source.write_text("same content", encoding="utf-8")

    first = stage_hris_txt_files((source,), tmp_path / "output", "HO")
    second = stage_hris_txt_files((source,), tmp_path / "output", "HO")

    assert first[0].status == "COPIED"
    assert second[0].status == "SKIPPED_IDENTICAL"
    assert second[0].destination_path == first[0].destination_path
    assert list(first[0].destination_path.parent.glob("*.txt")) == [
        first[0].destination_path
    ]


def test_stage_txt_renames_different_duplicate_without_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "same.txt"
    source.parent.mkdir()
    source.write_text("new content", encoding="utf-8")
    target = tmp_path / "output" / "HRIS" / "HO"
    target.mkdir(parents=True)
    existing = target / "same.txt"
    existing.write_text("old content", encoding="utf-8")

    result = stage_hris_txt_files((source,), tmp_path / "output", "HO")

    assert result[0].status == "COPIED_RENAMED"
    assert result[0].destination_path == target / "same_001.txt"
    assert existing.read_text(encoding="utf-8") == "old content"
    assert result[0].destination_path.read_text(encoding="utf-8") == "new content"


def test_stage_txt_ignores_non_txt_files(tmp_path: Path) -> None:
    source = tmp_path / "report.xlsx"
    source.write_text("not txt", encoding="utf-8")

    result = stage_hris_txt_files((source,), tmp_path / "output", "HO")

    assert result == ()
    assert not (tmp_path / "output").exists()
