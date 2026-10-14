"""Typed UI5 Outlook Revisi adapter and service contracts."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

TARGET_MAILBOX_SMTP = "karina.hr.1@oto.co.id"
TARGET_MAILBOX_DISPLAY = "RPA.HR01"
TARGET_FOLDER = "Inbox"


@dataclass(frozen=True, slots=True)
class OutlookRevisiRunRequest:
    configuration_path: Path | None
    workflow: str
    use_global_output: bool
    use_global_period: bool
    override_output_root: Path | None
    override_period_start: str | None
    override_period_end: str | None
    dry_run: bool = True
    message_limit: int | None = 25
    payroll_period: str | None = None


@dataclass(frozen=True, slots=True)
class OutlookRevisiResolvedRequest:
    job_id: str
    database_path: Path | None
    configuration_path: Path | None
    workflow: str
    output_root: Path
    period_start: str
    period_end: str
    payroll_period: str
    used_global_output: bool
    used_global_period: bool
    dry_run: bool
    message_limit: int | None
    outbound_requires_confirmation: bool = False
    outbound_acknowledged: bool = False
    send_typed_confirmed: bool = False

    @property
    def configuration_source(self) -> str:
        return "EXCEL_FALLBACK" if self.configuration_path is not None else "SQLITE"


@dataclass(frozen=True, slots=True)
class OutboundSafetyState:
    auto_reply_enabled: bool
    send_mode: str
    effective_mode: str
    reply_enabled: bool
    summary_email_enabled: bool
    recipients: tuple[str, ...] = ()
    requires_confirmation: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MailboxValidationResult:
    valid: bool
    configured_mailbox: str
    configured_folder: str
    outlook_status: str
    mailbox_found: bool
    folder_found: bool
    mailbox_display: str = ""
    error: str | None = None


@dataclass(frozen=True, slots=True)
class OutlookRevisiValidationResult:
    valid: bool
    configuration_valid: bool
    workflow: str
    period_start: str
    period_end: str
    output_root: Path
    mailbox: MailboxValidationResult
    outbound: OutboundSafetyState
    sender_count: int = 0
    subject_rule_count: int = 0
    attachment_rule_count: int = 0
    validation_rule_count: int = 0
    reply_template_count: int = 0
    summary_recipient_count: int = 0
    template_previews: tuple[tuple[str, str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OutlookRevisiProgressEvent:
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class OutlookRevisiLogEvent:
    timestamp: str
    level: str
    message: str


@dataclass(frozen=True, slots=True)
class OutlookRevisiOutputFile:
    file_type: str
    path: Path


@dataclass(frozen=True, slots=True)
class OutlookRevisiRunResult:
    success: bool
    cancelled: bool
    job_id: str
    workflow: str
    mailbox: str
    started_at: str
    ended_at: str
    output_root: Path
    job_folder: Path | None
    message_counts: dict[str, int]
    attachment_counts: dict[str, int]
    reply_counts: dict[str, int]
    output_files: tuple[OutlookRevisiOutputFile, ...]
    warning_count: int = 0
    error_summary: str | None = None
    process_log_path: Path | None = None
    summary_json_path: Path | None = None
    attachment_folder: Path | None = None


@dataclass(slots=True)
class OutlookRevisiCancellationToken:
    _event: threading.Event = field(default_factory=threading.Event)

    def request(self) -> None:
        self._event.set()

    @property
    def requested(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class OutlookRevisiDefaults:
    database_available: bool
    database_path: Path | None
    use_global_output: bool = False
    use_global_period: bool = False
    global_output_root: Path | None = None
    global_period_start: str | None = None
    global_period_end: str | None = None
    payroll_period: str | None = None
    resubmit_deadline: str | None = None
    warning: str = ""
