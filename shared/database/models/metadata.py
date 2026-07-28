"""Typed metadata and validation results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatabaseMetadata:
    """One database metadata singleton row."""

    database_uuid: str
    schema_version: int
    application_version: str
    created_at: str
    updated_at: str
    last_migrated_at: str | None
    metadata_id: int = 1


@dataclass(frozen=True, slots=True)
class DatabaseValidationResult:
    """Detailed, UI-ready database validation outcome."""

    database_path: Path
    is_valid: bool
    file_exists: bool
    file_readable: bool
    sqlite_header_ok: bool
    integrity_ok: bool
    foreign_keys_ok: bool
    schema_version: int | None
    missing_tables: tuple[str, ...] = ()
    missing_indexes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BackupResult:
    """Metadata for one validated SQLite backup."""

    source_path: Path
    destination_path: Path
    created_at: str
    file_size: int
    sha256: str
    schema_version: int
    validation: DatabaseValidationResult
