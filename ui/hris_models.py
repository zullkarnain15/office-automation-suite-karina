"""Typed HRIS UI6 requests, state, events, and results."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class HRISJobState(StrEnum):
    IDLE = "IDLE"
    VALIDATING = "VALIDATING"
    READY = "READY"
    STARTING_BROWSER = "STARTING_BROWSER"
    WAITING_FOR_LOGIN = "WAITING_FOR_LOGIN"
    NAVIGATING = "NAVIGATING"
    FILLING_RUN_CONTROL = "FILLING_RUN_CONTROL"
    FILLING_PERIOD = "FILLING_PERIOD"
    SELECTING_ATTACHMENT = "SELECTING_ATTACHMENT"
    WAITING_FOR_USER_UPLOAD = "WAITING_FOR_USER_UPLOAD"
    WAITING_FOR_CHECKPOINT = "WAITING_FOR_CHECKPOINT"
    WAITING_FOR_VERIFICATION = "WAITING_FOR_VERIFICATION"
    RESUMING = "RESUMING"
    RUNNING_REQUEST = "RUNNING_REQUEST"
    VERIFYING = "VERIFYING"
    FILE_COMPLETED = "FILE_COMPLETED"
    NEXT_FILE = "NEXT_FILE"
    COMPLETED = "COMPLETED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


TERMINAL_HRIS_STATES = {
    HRISJobState.COMPLETED,
    HRISJobState.CANCELLED,
    HRISJobState.FAILED,
}


@dataclass(frozen=True, slots=True)
class HRISRunRequest:
    source_folder: Path
    workflow: str
    use_global_period: bool
    period_start: str | None
    period_end: str | None
    recorder_profile: Path | None
    manual_upload_acknowledged: bool
    configuration_path: Path | None = None
    manual_login: bool = True
    login_id: str | None = None
    login_secret: str | None = None


@dataclass(frozen=True, slots=True)
class HRISResolvedRequest:
    job_id: str
    database_path: Path
    data_root: Path
    configuration_path: Path | None
    source_folder: Path
    output_root: Path
    workflow: str
    period_start: str
    period_end: str
    used_global_period: bool
    recorder_profile: Path
    manual_login: bool = True
    login_id: str | None = None
    login_secret: str | None = None


@dataclass(frozen=True, slots=True)
class HRISRunControlMapping:
    sequence: int
    txt_file: Path
    run_control_id: str
    workflow: str
    active: bool = True
    mapping_status: str = "READY"


@dataclass(frozen=True, slots=True)
class HRISRecorderProfile:
    name: str
    relative_path: Path
    absolute_path: Path
    workflow: str | None
    exists: bool
    json_valid: bool
    modified_at: float | None
    validation_status: str
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HRISDefaults:
    database_available: bool
    database_path: Path | None
    data_root: Path | None
    hris_url: str = ""
    browser: str = "msedge"
    output_root: Path | None = None
    use_global_period: bool = False
    global_period_start: str | None = None
    global_period_end: str | None = None
    recorder_profile: Path | None = None
    ho_run_controls: tuple[str, ...] = ()
    branch_run_controls: tuple[str, ...] = ()
    assisted_steps_count: int = 0
    last_updated: str | None = None
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class HRISValidationResult:
    valid: bool
    browser_allowed: bool
    workflow: str
    period_start: str
    period_end: str
    txt_count: int
    mappings: tuple[HRISRunControlMapping, ...]
    profile: HRISRecorderProfile | None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HRISProgressEvent:
    state: HRISJobState
    message: str
    completed_files: int = 0
    total_files: int = 0


@dataclass(frozen=True, slots=True)
class HRISLogEvent:
    timestamp: str
    level: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class HRISInterventionRequest:
    job_id: str
    state: HRISJobState
    message: str
    txt_file: Path | None = None
    run_control_id: str | None = None
    actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HRISInterventionResponse:
    accepted: bool
    message: str = ""


@dataclass(frozen=True, slots=True)
class HRISFileResult:
    source_path: Path
    run_control_id: str
    status: str
    message: str
    uploaded_path: Path | None = None


@dataclass(frozen=True, slots=True)
class HRISRunResult:
    success: bool
    cancelled: bool
    job_id: str
    workflow: str
    started_at: str
    ended_at: str
    files: tuple[HRISFileResult, ...]
    report_path: Path | None = None
    summary_json_path: Path | None = None
    process_log_path: Path | None = None
    output_folder: Path | None = None
    error_summary: str | None = None


class HRISCancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def request(self) -> None:
        self._event.set()


@dataclass(slots=True)
class HRISInteractionGate:
    login_event: threading.Event = field(default_factory=threading.Event)
    upload_event: threading.Event = field(default_factory=threading.Event)
    upload_failed_event: threading.Event = field(default_factory=threading.Event)
    upload_failure_message: str = ""
    current_intervention: HRISInterventionRequest | None = None
    decision_event: threading.Event = field(default_factory=threading.Event)
    decision_action: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def wait(self, event: threading.Event, cancellation: HRISCancellationToken) -> None:
        while not event.wait(0.1):
            if cancellation.requested:
                raise HRISCancelledError("HRIS job dibatalkan pada safe checkpoint.")
        if cancellation.requested:
            raise HRISCancelledError("HRIS job dibatalkan pada safe checkpoint.")

    def prepare_upload(self, intervention: HRISInterventionRequest) -> None:
        with self._lock:
            self.current_intervention = intervention
            self.upload_event.clear()
            self.upload_failed_event.clear()
            self.upload_failure_message = ""

    def confirm_login(self) -> None:
        self.login_event.set()

    def confirm_upload(self) -> None:
        self.upload_event.set()

    def fail_upload(self, message: str) -> None:
        self.upload_failure_message = message
        self.upload_failed_event.set()
        self.upload_event.set()

    def prepare_decision(self, intervention: HRISInterventionRequest) -> None:
        with self._lock:
            self.current_intervention = intervention
            self.decision_action = ""
            self.decision_event.clear()

    def choose(self, action: str) -> None:
        with self._lock:
            self.decision_action = action
            self.decision_event.set()


class HRISCancelledError(RuntimeError):
    """Raised only at a cooperative HRIS checkpoint."""
