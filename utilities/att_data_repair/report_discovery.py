"""Discover Attachment Consolidation Excel reports from a source folder."""

from __future__ import annotations

import re
from pathlib import Path

from utilities.att_data_repair.constants import INVALID_RECORDS_SHEET, VALID_RECORDS_SHEET
from utilities.att_data_repair.models import (
    MissingRequiredColumnError,
    MissingRequiredSheetError,
    ReportDiscoveryCandidate,
    ReportDiscoveryResult,
    SourceWorkbookError,
)
from utilities.att_data_repair.report_reader import AttDataRepairReportReader

REPORT_EXTENSIONS = frozenset({".xlsx"})
TEMP_FILE_PREFIX = "~$"


class AttDataRepairReportDiscovery:
    """Find and validate source reports without mutating source files."""

    def __init__(self, reader: AttDataRepairReportReader | None = None) -> None:
        self.reader = reader or AttDataRepairReportReader()

    def discover(
        self,
        source_folder: str | Path,
        *,
        recursive: bool = True,
    ) -> ReportDiscoveryResult:
        folder = Path(source_folder)
        if not folder.is_dir():
            raise NotADirectoryError(f"Source folder tidak ditemukan: {folder}")

        pattern = "**/*" if recursive else "*"
        candidates: list[ReportDiscoveryCandidate] = []
        skipped_temp_files = 0
        for path in sorted(folder.glob(pattern), key=lambda item: str(item).casefold()):
            if not path.is_file():
                continue
            if path.name.startswith(TEMP_FILE_PREFIX):
                skipped_temp_files += 1
                continue
            if path.suffix.casefold() not in REPORT_EXTENSIONS:
                continue
            candidates.append(self._inspect(folder, path))

        return ReportDiscoveryResult(
            source_folder=folder,
            recursive=recursive,
            candidates=tuple(candidates),
            skipped_temp_files=skipped_temp_files,
        )

    def _inspect(self, root: Path, path: Path) -> ReportDiscoveryCandidate:
        try:
            records = self.reader.read(path)
        except MissingRequiredSheetError:
            return self._candidate(
                root,
                path,
                "INVALID",
                "Sheet Valid_Records atau Invalid_Records tidak ditemukan.",
            )
        except MissingRequiredColumnError:
            return self._candidate(
                root,
                path,
                "INVALID",
                "Kolom wajib report tidak lengkap.",
            )
        except SourceWorkbookError:
            return self._candidate(
                root,
                path,
                "INVALID",
                "File tidak dapat dibaca sebagai Excel Report Attachment Consolidation.",
            )

        valid_count = sum(
            1
            for record in records
            if _same_sheet(record.source_sheet, VALID_RECORDS_SHEET)
        )
        invalid_count = sum(
            1
            for record in records
            if _same_sheet(record.source_sheet, INVALID_RECORDS_SHEET)
        )
        if not records:
            return self._candidate(root, path, "INVALID", "Report tidak berisi record.")
        return self._candidate(
            root,
            path,
            "VALID",
            "Excel Report Attachment Consolidation valid.",
            record_count=len(records),
            valid_records_count=valid_count,
            invalid_records_count=invalid_count,
        )

    @staticmethod
    def _candidate(
        root: Path,
        path: Path,
        status: str,
        reason: str,
        *,
        record_count: int = 0,
        valid_records_count: int = 0,
        invalid_records_count: int = 0,
    ) -> ReportDiscoveryCandidate:
        try:
            relative = str(path.relative_to(root))
        except ValueError:
            relative = path.name
        return ReportDiscoveryCandidate(
            path=path,
            relative_path=relative,
            status=status,
            reason=reason,
            record_count=record_count,
            valid_records_count=valid_records_count,
            invalid_records_count=invalid_records_count,
            size_bytes=path.stat().st_size if path.exists() else 0,
        )


def _same_sheet(actual: str, expected: str) -> bool:
    return _normalize_name(actual) == _normalize_name(expected)


def _normalize_name(value: object) -> str:
    return re.sub(r"[\s_]+", "", str(value or "")).casefold()
