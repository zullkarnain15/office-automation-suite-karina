"""Domain exceptions for configuration workbook exports."""

from shared.database.exceptions import DatabaseErrorBase


class ConfigExportError(DatabaseErrorBase):
    """Raised when a configuration export cannot be completed safely."""


class WorkbookValidationError(ConfigExportError):
    """Raised when a generated workbook violates the DB2B contract."""


class LegacyExportUnsupportedError(ConfigExportError):
    """Raised when a lossless legacy representation is not safe."""
