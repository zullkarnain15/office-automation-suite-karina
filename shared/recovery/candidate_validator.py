"""Read-only candidate database validation."""

from __future__ import annotations

from pathlib import Path

from shared.database import DatabaseValidator, SCHEMA_VERSION
from shared.recovery.models import CandidateValidationResult


class CandidateValidator:
    def __init__(self, validator: DatabaseValidator | None = None) -> None:
        self.validator = validator or DatabaseValidator()

    def validate(self, candidate_path: str | Path) -> CandidateValidationResult:
        path = Path(candidate_path).expanduser()
        result = self.validator.validate(path)
        metadata_ok = result.schema_version is not None
        schema_compatible = result.schema_version == SCHEMA_VERSION
        sqlite_valid = result.sqlite_header_ok
        return CandidateValidationResult(
            candidate_path=path,
            exists=result.file_exists,
            readable=result.file_readable,
            sqlite_valid=sqlite_valid,
            integrity_ok=result.integrity_ok,
            foreign_keys_ok=result.foreign_keys_ok,
            schema_version=result.schema_version,
            schema_compatible=schema_compatible,
            required_tables_ok=not result.missing_tables,
            metadata_ok=metadata_ok,
            warnings=result.warnings,
            errors=result.errors,
        )


def validate_candidate(path: str | Path) -> CandidateValidationResult:
    return CandidateValidator().validate(path)
