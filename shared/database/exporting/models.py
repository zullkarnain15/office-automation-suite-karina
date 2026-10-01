"""Typed results for configuration workbook generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.database.importing.models import WorkbookIdentity


@dataclass(frozen=True, slots=True)
class WorkbookValidationResult:
    path: Path
    is_valid: bool
    sheet_names: tuple[str, ...]
    formula_count: int
    external_link_count: int
    has_macros: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportResult:
    output_path: Path
    workbook_identity: WorkbookIdentity
    sheet_names: tuple[str, ...]
    validation: WorkbookValidationResult
    exported_at: str
