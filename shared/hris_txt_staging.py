"""Copy generated HRIS TXT files into the workflow upload queue."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HRISTXTStagingResult:
    source_path: Path
    destination_path: Path
    status: str


def stage_hris_txt_files(
    source_files: tuple[Path, ...],
    output_root: Path,
    workflow: str,
) -> tuple[HRISTXTStagingResult, ...]:
    """Copy TXT files into output/HRIS/<workflow> without overwriting."""
    txt_files = tuple(
        Path(source)
        for source in source_files
        if Path(source).suffix.casefold() == ".txt"
    )
    if not txt_files:
        return ()

    target_folder = _target_folder(output_root, workflow)
    target_folder.mkdir(parents=True, exist_ok=True)

    results: list[HRISTXTStagingResult] = []
    for source_path in txt_files:
        if not source_path.is_file():
            raise FileNotFoundError(f"HRIS TXT source tidak ditemukan: {source_path}")

        destination, status = _select_destination(source_path, target_folder)
        if status != "SKIPPED_IDENTICAL":
            _copy_exclusive(source_path, destination)
        results.append(HRISTXTStagingResult(source_path, destination, status))

    return tuple(results)


def _target_folder(output_root: Path, workflow: str) -> Path:
    normalized = workflow.strip().upper()
    if normalized not in {"HO", "BRANCH"}:
        raise ValueError("Workflow staging HRIS harus HO atau BRANCH.")
    hris_root = output_root if output_root.name.casefold() == "hris" else output_root / "HRIS"
    return hris_root / ("HO" if normalized == "HO" else "Branch")


def _select_destination(source: Path, target_folder: Path) -> tuple[Path, str]:
    direct = target_folder / source.name
    if not direct.exists():
        return direct, "COPIED"
    if direct.is_file() and _same_content(source, direct):
        return direct, "SKIPPED_IDENTICAL"

    counter = 1
    while True:
        candidate = target_folder / f"{source.stem}_{counter:03d}{source.suffix}"
        if not candidate.exists():
            return candidate, "COPIED_RENAMED"
        if candidate.is_file() and _same_content(source, candidate):
            return candidate, "SKIPPED_IDENTICAL"
        counter += 1


def _same_content(first: Path, second: Path) -> bool:
    if first.stat().st_size != second.stat().st_size:
        return False
    return _sha256(first) == _sha256(second)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_exclusive(source: Path, destination: Path) -> None:
    created = False
    try:
        with source.open("rb") as source_stream:
            with destination.open("xb") as destination_stream:
                created = True
                shutil.copyfileobj(source_stream, destination_stream)
        shutil.copystat(source, destination)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
