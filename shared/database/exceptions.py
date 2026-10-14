"""Domain exceptions for the OAS-K SQLite foundation."""

from __future__ import annotations


class DatabaseErrorBase(Exception):
    """Base class for database-layer errors."""


class DatabaseInitializationError(DatabaseErrorBase):
    """Raised when an OAS-K database cannot be initialized safely."""


class DatabaseValidationError(DatabaseErrorBase):
    """Raised when a database fails structural or integrity validation."""


class SchemaMismatchError(DatabaseErrorBase):
    """Raised when a database schema version is incompatible."""


class MigrationError(DatabaseErrorBase):
    """Raised when the migration contract cannot be satisfied."""


class StartupDatabaseMigrationError(DatabaseErrorBase):
    """Raised when startup cannot safely prepare the active database."""


class BackupError(DatabaseErrorBase):
    """Raised when SQLite backup creation or validation fails."""


class RepositoryError(DatabaseErrorBase):
    """Raised when a typed repository operation fails."""
