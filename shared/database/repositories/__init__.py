"""Typed repositories for the OAS-K SQLite foundation."""

from shared.database.repositories.audit_repository import AuditRepository
from shared.database.repositories.application_preferences_repository import (
    ApplicationPreferencesRepository,
)
from shared.database.repositories.backup_history_repository import (
    BackupHistoryRepository,
)
from shared.database.repositories.global_settings_repository import (
    GlobalSettingsRepository,
)
from shared.database.repositories.job_repository import JobRepository
from shared.database.repositories.metadata_repository import (
    MetadataRepository,
)

__all__ = [
    "ApplicationPreferencesRepository",
    "AuditRepository",
    "BackupHistoryRepository",
    "GlobalSettingsRepository",
    "JobRepository",
    "MetadataRepository",
]
