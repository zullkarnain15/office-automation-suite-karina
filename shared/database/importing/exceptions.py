"""Exceptions raised by the DB2 configuration import boundary."""

from __future__ import annotations

from shared.database.exceptions import DatabaseErrorBase


class ConfigImportError(DatabaseErrorBase):
    """Base configuration import error."""


class WorkbookDetectionError(ConfigImportError):
    """Workbook identity is unknown or ambiguous."""


class WorkbookReadError(ConfigImportError):
    """Workbook cannot be read safely."""


class ConfigValidationError(ConfigImportError):
    """Mapped configuration is invalid."""


class ConfigCommitError(ConfigImportError):
    """A preview cannot be committed safely."""


class ConfigExportError(DatabaseErrorBase):
    """Configuration workbook export failed."""
