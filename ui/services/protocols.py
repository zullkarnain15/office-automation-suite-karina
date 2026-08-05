"""Protocols and typed view models for injected Settings services."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ui.attendance_models import (
    AttendanceCancellationToken,
    AttendanceDefaults,
    AttendanceLogEvent,
    AttendanceProgressEvent,
    AttendanceResolvedRequest,
    AttendanceRunRequest,
    AttendanceRunResult,
    AttendanceValidationResult,
)
from ui.outlook_revisi_models import (
    OutboundSafetyState,
    OutlookRevisiCancellationToken,
    OutlookRevisiDefaults,
    OutlookRevisiLogEvent,
    OutlookRevisiProgressEvent,
    OutlookRevisiResolvedRequest,
    OutlookRevisiRunRequest,
    OutlookRevisiRunResult,
    OutlookRevisiValidationResult,
)
from ui.hris_models import (
    HRISCancellationToken,
    HRISDefaults,
    HRISProgressEvent,
    HRISResolvedRequest,
    HRISRunRequest,
    HRISRunResult,
)
from ui.utilities_models import (
    AttachmentConsolidationCancellationToken,
    AttachmentConsolidationProgressEvent,
    AttachmentConsolidationResolvedRequest,
    AttachmentConsolidationRunRequest,
    AttachmentConsolidationRunResult,
    ComparisonCancellationToken,
    ComparisonProgressEvent,
    ComparisonResolvedRequest,
    ComparisonRunRequest,
    ComparisonRunResult,
    UtilitiesDefaults,
    UtilitiesFeatureSummary,
)


@dataclass(frozen=True, slots=True)
class GlobalSettingsDraft:
    output_root: str = ""
    period_start: str | None = None
    period_end: str | None = None


@dataclass(frozen=True, slots=True)
class OutlookOperationalSettingsDraft:
    payroll_period: str = ""
    resubmit_deadline: str = ""


@dataclass(frozen=True, slots=True)
class ModuleGlobalUsage:
    module: str
    label: str
    use_global_output: bool
    use_global_period: bool | None
    available: bool = True


@dataclass(frozen=True, slots=True)
class StorageStatusView:
    resolution_status: str
    data_root: Path | None
    database_path: Path | None
    database_exists: bool
    database_valid: bool
    schema_version: int | None
    application_version: str | None
    registry_status: str
    recorder_profiles_folder: Path | None
    backup_folder: Path | None
    output_folder: Path | None
    logs_folder: Path | None
    diagnostics_folder: Path | None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecorderProfileItem:
    filename: str
    relative_path: Path
    modified_at: float
    valid: bool


class DatabaseSettingsServiceProtocol(Protocol):
    def load_global_settings(self, database_path: Path) -> GlobalSettingsDraft: ...

    def save_global_settings(
        self,
        database_path: Path,
        draft: GlobalSettingsDraft,
        *,
        operator: str | None = None,
    ) -> GlobalSettingsDraft: ...

    def load_outlook_operational_settings(
        self,
        database_path: Path,
    ) -> OutlookOperationalSettingsDraft: ...

    def save_outlook_operational_settings(
        self,
        database_path: Path,
        draft: OutlookOperationalSettingsDraft,
        *,
        operator: str | None = None,
    ) -> OutlookOperationalSettingsDraft: ...

    def load_module_global_usage(
        self,
        database_path: Path,
    ) -> tuple[ModuleGlobalUsage, ...]: ...

    def save_module_global_usage(
        self,
        database_path: Path,
        values: Sequence[ModuleGlobalUsage],
        *,
        operator: str | None = None,
    ) -> tuple[ModuleGlobalUsage, ...]: ...

    def validate_database(self, database_path: Path) -> Any: ...


class StorageUIServiceProtocol(Protocol):
    def resolve_status(self) -> StorageStatusView: ...

    def initialize(self, data_root: Path, *, write_registry: bool) -> Any: ...

    def relocate(self, request: Any) -> Any: ...


class ModuleConfigurationServiceProtocol(Protocol):
    def load_summaries(self, database_path: Path | None) -> tuple[Any, ...]: ...

    def load_detail(self, database_path: Path, module: str) -> Any: ...


class AttendanceServiceProtocol(Protocol):
    def load_defaults(self) -> AttendanceDefaults: ...

    def resolve_request(
        self,
        request: AttendanceRunRequest,
        *,
        require_database: bool,
    ) -> AttendanceResolvedRequest: ...

    def preflight(
        self,
        request: AttendanceRunRequest,
        *,
        require_database: bool,
    ) -> tuple[AttendanceResolvedRequest, AttendanceValidationResult]: ...

    def run_job(
        self,
        resolved: AttendanceResolvedRequest,
        *,
        cancellation: AttendanceCancellationToken,
        progress: Callable[[AttendanceProgressEvent], None],
        log: Callable[[AttendanceLogEvent], None],
    ) -> AttendanceRunResult: ...

    def request_cancellation(
        self,
        resolved: AttendanceResolvedRequest,
        token: AttendanceCancellationToken,
    ) -> None: ...


class OutlookRevisiServiceProtocol(Protocol):
    def load_defaults(self) -> OutlookRevisiDefaults: ...

    def preflight(
        self,
        request: OutlookRevisiRunRequest,
        *,
        require_database: bool,
        check_mailbox: bool,
    ) -> tuple[OutlookRevisiResolvedRequest, OutlookRevisiValidationResult]: ...

    def confirm_outbound(
        self,
        resolved: OutlookRevisiResolvedRequest,
        safety: OutboundSafetyState,
        *,
        acknowledged: bool,
        typed_confirmed: bool,
    ) -> OutlookRevisiResolvedRequest: ...

    def run_job(
        self,
        resolved: OutlookRevisiResolvedRequest,
        *,
        cancellation: OutlookRevisiCancellationToken,
        progress: Callable[[OutlookRevisiProgressEvent], None],
        log: Callable[[OutlookRevisiLogEvent], None],
    ) -> OutlookRevisiRunResult: ...

    def request_cancellation(
        self,
        resolved: OutlookRevisiResolvedRequest,
        token: OutlookRevisiCancellationToken,
    ) -> None: ...


class HRISServiceProtocol(Protocol):
    def load_defaults(self) -> HRISDefaults: ...

    def preflight(self, request: HRISRunRequest) -> tuple[Any, Any]: ...

    def run_job(
        self,
        resolved: HRISResolvedRequest,
        *,
        cancellation: HRISCancellationToken,
        progress: Callable[[HRISProgressEvent], None],
        log: Callable[[Any], None],
        intervention: Callable[[Any], None],
    ) -> HRISRunResult: ...

    def confirm_login_complete(self, job_id: str) -> None: ...

    def confirm_upload_complete(self, job_id: str) -> None: ...

    def report_upload_failed(self, job_id: str, message: str) -> None: ...

    def choose_intervention(self, job_id: str, action: str) -> None: ...

    def request_cancel(
        self,
        resolved: HRISResolvedRequest,
        token: HRISCancellationToken,
    ) -> None: ...


class UtilitiesServiceProtocol(Protocol):
    def landing_summaries(self) -> tuple[UtilitiesFeatureSummary, ...]: ...

    def load_defaults(self) -> UtilitiesDefaults: ...


class ComparisonResultServiceProtocol(Protocol):
    def load_defaults(self) -> UtilitiesDefaults: ...

    def preflight(
        self, request: ComparisonRunRequest, *, cancellation: ComparisonCancellationToken
    ) -> tuple[Any, Any]: ...

    def run_job(
        self, resolved: ComparisonResolvedRequest, validation: Any, *,
        cancellation: ComparisonCancellationToken,
        progress: Callable[[ComparisonProgressEvent], None],
        log: Callable[[Any], None],
    ) -> ComparisonRunResult: ...

    def request_cancellation(
        self, resolved: ComparisonResolvedRequest, token: ComparisonCancellationToken
    ) -> None: ...


class AttachmentConsolidationServiceProtocol(Protocol):
    def load_defaults(self) -> UtilitiesDefaults: ...

    def preflight(
        self, request: AttachmentConsolidationRunRequest, *,
        cancellation: AttachmentConsolidationCancellationToken,
    ) -> tuple[Any, Any]: ...

    def run_job(
        self, resolved: AttachmentConsolidationResolvedRequest, validation: Any, *,
        cancellation: AttachmentConsolidationCancellationToken,
        progress: Callable[[AttachmentConsolidationProgressEvent], None],
        log: Callable[[Any], None],
    ) -> AttachmentConsolidationRunResult: ...

    def request_cancellation(
        self, resolved: AttachmentConsolidationResolvedRequest,
        token: AttachmentConsolidationCancellationToken,
    ) -> None: ...


class DialogServiceProtocol(Protocol):
    def select_folder(self, *, title: str) -> Path | None: ...

    def select_file(
        self,
        *,
        title: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> Path | None: ...

    def select_files(
        self,
        *,
        title: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> tuple[Path, ...]: ...

    def save_file(
        self,
        *,
        title: str,
        default_name: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> Path | None: ...

    def confirm(self, title: str, message: str) -> bool: ...

    def typed_confirm(self, title: str, message: str, expected: str) -> bool: ...

    def prompt_text(self, title: str, message: str) -> str | None: ...

    def info(self, title: str, message: str) -> None: ...

    def completion(
        self, module_name: str, message: str, details: tuple[str, ...] = ()
    ) -> None: ...

    def warning(self, title: str, message: str) -> None: ...

    def error(self, title: str, message: str) -> None: ...


AfterCallback = Callable[[int, Callable[[], None]], Any]
