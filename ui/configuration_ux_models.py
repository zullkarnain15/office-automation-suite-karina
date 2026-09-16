"""User-facing configuration models for the UI5B presentation layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActiveConfigurationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INVALID = "INVALID"
    WARNING = "WARNING"
    UNAVAILABLE = "UNAVAILABLE"


class ConfigurationImportStep(StrEnum):
    SELECT_FILE = "SELECT_FILE"
    REVIEW = "REVIEW"
    APPLY = "APPLY"


class ConfigurationModuleStatus(StrEnum):
    READY = "READY"
    ATTENTION = "ATTENTION"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"


class ConfigurationConflictChoice(StrEnum):
    KEEP_CURRENT = "KEEP_CURRENT"
    USE_IMPORTED = "USE_IMPORTED"
    USE_ALTERNATE = "USE_ALTERNATE"


@dataclass(frozen=True, slots=True)
class ModuleConfigurationSummary:
    module: str
    title: str
    status: ActiveConfigurationStatus
    source: str
    fields: tuple[tuple[str, str], ...]
    last_updated: str | None = None
    warning: str | None = None

    @property
    def status_label(self) -> str:
        return {
            ActiveConfigurationStatus.ACTIVE: "Aktif",
            ActiveConfigurationStatus.NOT_CONFIGURED: "Belum Dikonfigurasi",
            ActiveConfigurationStatus.INVALID: "Tidak Valid",
            ActiveConfigurationStatus.WARNING: "Perlu Perhatian",
            ActiveConfigurationStatus.UNAVAILABLE: "Tidak Tersedia",
        }[self.status]


@dataclass(frozen=True, slots=True)
class ModuleConfigurationDetail:
    module: str
    title: str
    sections: tuple[tuple[str, tuple[dict[str, Any], ...]], ...]


@dataclass(frozen=True, slots=True)
class ConfigurationIssuePresentation:
    title: str
    detail: str
    severity: str
    technical_code: str


@dataclass(frozen=True, slots=True)
class ConfigurationImportUserSummary:
    modules: tuple[tuple[str, ConfigurationModuleStatus], ...]
    insert_count: int
    update_count: int
    delete_count: int
    warning_count: int
    error_count: int
    confirmation_required: bool
    issues: tuple[ConfigurationIssuePresentation, ...] = ()
