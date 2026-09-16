"""Typed persistence models exposed by :mod:`shared.database`."""

from shared.database.models.audit import (
    BackupHistoryRecord,
    ConfigurationAuditRecord,
)
from shared.database.models.global_settings import GlobalSettings
from shared.database.models.job import JobFileRecord, JobHistoryRecord
from shared.database.models.metadata import (
    BackupResult,
    DatabaseMetadata,
    DatabaseValidationResult,
)

__all__ = [
    "BackupHistoryRecord",
    "BackupResult",
    "ConfigurationAuditRecord",
    "DatabaseMetadata",
    "DatabaseValidationResult",
    "GlobalSettings",
    "JobFileRecord",
    "JobHistoryRecord",
]
