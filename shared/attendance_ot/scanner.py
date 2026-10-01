"""Recursive, deterministic source discovery with streaming fingerprints."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from shared.attendance_ot.models import ScanIssue, SourceCandidate, SourceType

SUPPORTED_EXTENSIONS = frozenset({".xlsx", ".xls"})
FINGERPRINT_CHUNK_SIZE = 1024 * 1024


def fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(FINGERPRINT_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def scan_source_folder(
    root: Path, source_type: SourceType
) -> tuple[tuple[SourceCandidate, ...], tuple[ScanIssue, ...]]:
    root = Path(root).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"Source folder tidak ditemukan: {root}")
    candidates: list[SourceCandidate] = []
    issues: list[ScanIssue] = []
    for current_root, directories, files in os.walk(root):
        directories.sort(key=str.casefold)
        for filename in sorted(files, key=str.casefold):
            if filename.startswith("~$"):
                continue
            path = Path(current_root) / filename
            if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                stat = path.stat()
                candidates.append(
                    SourceCandidate(
                        source_type=source_type,
                        path=path.resolve(),
                        filename=filename,
                        size_bytes=stat.st_size,
                        modified_time_ns=stat.st_mtime_ns,
                        fingerprint=fingerprint_file(path),
                    )
                )
            except OSError as exc:
                issues.append(
                    ScanIssue(
                        source_type,
                        path.resolve(),
                        filename,
                        f"File tidak dapat dibaca: {exc}",
                    )
                )
    return tuple(candidates), tuple(issues)
