"""SQLite core for Office Automation Suite - Karina.

Importing this package has no database, Registry, GUI, or engine side effects.
"""

from shared.database.backup_manager import BackupManager
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.constants import REQUIRED_TABLES, SCHEMA_VERSION
from shared.database.database_validator import DatabaseValidator
from shared.database.exceptions import (
    BackupError,
    DatabaseErrorBase,
    DatabaseInitializationError,
    DatabaseValidationError,
    MigrationError,
    RepositoryError,
    SchemaMismatchError,
    StartupDatabaseMigrationError,
)
from shared.database.migration_manager import MigrationManager
from shared.database.schema_manager import SchemaManager
from shared.database.startup_migration import (
    StartupDatabaseMigrator,
    StartupMigrationResult,
)

__all__ = [
    "BackupError",
    "BackupManager",
    "DatabaseErrorBase",
    "DatabaseInitializationError",
    "DatabaseValidationError",
    "DatabaseValidator",
    "MigrationError",
    "MigrationManager",
    "REQUIRED_TABLES",
    "RepositoryError",
    "SCHEMA_VERSION",
    "SQLiteConnectionFactory",
    "SchemaManager",
    "SchemaMismatchError",
    "StartupDatabaseMigrationError",
    "StartupDatabaseMigrator",
    "StartupMigrationResult",
]
