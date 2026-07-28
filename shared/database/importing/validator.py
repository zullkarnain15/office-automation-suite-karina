"""Structured validation for mapped configuration rows."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

from shared.database.importing.models import (
    ConfigImportIssue,
    IssueSeverity,
    MappedModuleConfiguration,
)
from shared.payroll_period import normalize_payroll_period

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Z0-9_]+)\}")
ALLOWED_REPLY_PLACEHOLDERS = {
    "ERROR_REASON",
    "EXPECTED_SUBJECT",
    "FAILED_EMAIL",
    "ORIGINAL_SUBJECT",
    "OUTPUT_FOLDER",
    "OUTPUT_TXT_COUNT",
    "PERIOD",
    "REQUIRED_CC_EMAIL",
    "RESUBMIT_DEADLINE",
    "SENDER_NAME",
    "SUCCESS_EMAIL",
    "TOTAL_EMAIL",
}
ASSISTED_ACTIONS = {
    "click",
    "click_type",
    "type",
    "press",
    "attach_file",
    "wait",
    "manual_continue",
}
ASSISTED_METHODS = {"coordinate", "playwright", "manual", "assisted"}
ASSISTED_SOURCES = {
    "NONE",
    "RUN_CONTROL_ID",
    "START_DATE",
    "END_DATE",
    "TXT_FILE_PATH",
}


def validate_mapped_configuration(
    mapped: MappedModuleConfiguration,
) -> tuple[ConfigImportIssue, ...]:
    """Return validation issues without mutating the mapped payload."""

    issues: list[ConfigImportIssue] = list(mapped.issues)
    if mapped.module == "ATTENDANCE":
        _validate_attendance(mapped, issues)
    elif mapped.module == "OUTLOOK_REVISI":
        _validate_outlook(mapped, issues)
    elif mapped.module == "HRIS":
        _validate_hris(mapped, issues)
    elif mapped.module == "UTILITIES":
        _validate_utilities(mapped, issues)
    return tuple(issues)


def _validate_attendance(
    mapped: MappedModuleConfiguration,
    issues: list[ConfigImportIssue],
) -> None:
    settings_rows = mapped.tables["attendance_settings"]
    if not settings_rows:
        issues.append(_error("ATTENDANCE_SETTINGS_REQUIRED", "ATTENDANCE"))
        return
    settings = settings_rows[0]
    if int(settings["split_txt_rows"]) <= 0:
        issues.append(_error("ATTENDANCE_SPLIT_LIMIT_INVALID", "ATTENDANCE"))
    sources = mapped.tables["attendance_sources"]
    keys = [(row["workflow"], row["source_code"]) for row in sources]
    _duplicates(keys, "ATTENDANCE_SOURCE_DUPLICATE", "ATTENDANCE", issues)
    for row in sources:
        if row["is_active"] and not row["mdb_path"]:
            issues.append(
                _error(
                    "ATTENDANCE_SOURCE_PATH_REQUIRED",
                    "ATTENDANCE",
                    field="mdb_path",
                    value=row["source_code"],
                )
            )


def _validate_outlook(
    mapped: MappedModuleConfiguration,
    issues: list[ConfigImportIssue],
) -> None:
    settings_rows = mapped.tables["outlook_settings"]
    if not settings_rows:
        issues.append(_error("OUTLOOK_SETTINGS_REQUIRED", "OUTLOOK_REVISI"))
        return
    settings = settings_rows[0]
    mailbox = str(settings["mailbox_smtp"])
    if not EMAIL_PATTERN.fullmatch(mailbox):
        issues.append(
            _error(
                "OUTLOOK_MAILBOX_INVALID",
                "OUTLOOK_REVISI",
                field="mailbox_smtp",
                value=mailbox,
            )
        )
    if not str(settings["source_folder"]).strip():
        issues.append(_error("OUTLOOK_SOURCE_FOLDER_REQUIRED", "OUTLOOK_REVISI"))
    try:
        normalize_payroll_period(settings.get("payroll_period"))
    except ValueError as exc:
        issues.append(
            _error(
                "OUTLOOK_PAYROLL_PERIOD_INVALID",
                "OUTLOOK_REVISI",
                field="payroll_period",
                value=settings.get("payroll_period"),
                message=str(exc),
            )
        )

    sender_keys = [
        (
            row["workflow"],
            row["company_code"],
            row["branch_code"],
            str(row["sender_email"]).casefold(),
        )
        for row in mapped.tables["outlook_sender_master"]
    ]
    _duplicates(sender_keys, "OUTLOOK_SENDER_DUPLICATE", "OUTLOOK_REVISI", issues)
    subject_keys = [
        (row["workflow"], row["subject_pattern"])
        for row in mapped.tables["outlook_subject_rules"]
    ]
    _duplicates(
        subject_keys,
        "OUTLOOK_SUBJECT_RULE_DUPLICATE",
        "OUTLOOK_REVISI",
        issues,
    )
    for row in mapped.tables["outlook_attachment_rules"]:
        extension = str(row["extension"])
        if not extension.startswith(".") or any(
            char in extension for char in ("/", "\\", ";")
        ):
            issues.append(
                _error(
                    "OUTLOOK_ATTACHMENT_EXTENSION_INVALID",
                    "OUTLOOK_REVISI",
                    field="extension",
                    value=extension,
                )
            )

    for row in mapped.tables["outlook_reply_templates"]:
        text = (
            str(row.get("subject_template") or "")
            + "\n"
            + str(row["body_template"])
        )
        unknown = sorted(
            set(PLACEHOLDER_PATTERN.findall(text))
            - ALLOWED_REPLY_PLACEHOLDERS
        )
        if unknown:
            issues.append(
                ConfigImportIssue(
                    code="UNKNOWN_REPLY_TEMPLATE_PLACEHOLDER",
                    severity=IssueSeverity.ERROR,
                    module="OUTLOOK_REVISI",
                    field="body_template",
                    message="Unknown reply template placeholder.",
                    current_value=",".join(unknown),
                )
            )


def _validate_hris(
    mapped: MappedModuleConfiguration,
    issues: list[ConfigImportIssue],
) -> None:
    settings_rows = mapped.tables["hris_settings"]
    if not settings_rows:
        issues.append(_error("HRIS_SETTINGS_REQUIRED", "HRIS"))
        return
    settings = settings_rows[0]
    parsed = urlsplit(str(settings["hris_url"]))
    if not parsed.scheme:
        issues.append(
            _error("HRIS_URL_INVALID", "HRIS", field="hris_url")
        )
    controls = mapped.tables["hris_run_controls"]
    _duplicates(
        [(row["workflow"], row["run_control_id"]) for row in controls],
        "HRIS_RUN_CONTROL_DUPLICATE",
        "HRIS",
        issues,
    )
    _duplicates(
        [(row["workflow"], row["sequence"]) for row in controls],
        "HRIS_RUN_CONTROL_SEQUENCE_DUPLICATE",
        "HRIS",
        issues,
    )
    for row in controls:
        if not str(row["run_control_id"]):
            issues.append(_error("HRIS_RUN_CONTROL_ID_REQUIRED", "HRIS"))
        if int(row["sequence"]) <= 0:
            issues.append(_error("HRIS_RUN_CONTROL_SEQUENCE_INVALID", "HRIS"))

    steps = mapped.tables["hris_assisted_steps"]
    _duplicates(
        [row["step_name"] for row in steps],
        "HRIS_ASSISTED_STEP_DUPLICATE",
        "HRIS",
        issues,
    )
    _duplicates(
        [row["sequence"] for row in steps],
        "HRIS_ASSISTED_SEQUENCE_DUPLICATE",
        "HRIS",
        issues,
    )
    for row in steps:
        if row["action"] not in ASSISTED_ACTIONS:
            issues.append(_error("HRIS_ASSISTED_ACTION_INVALID", "HRIS"))
        if row["method"] not in ASSISTED_METHODS:
            issues.append(_error("HRIS_ASSISTED_METHOD_INVALID", "HRIS"))
        if row["input_source"] not in ASSISTED_SOURCES:
            issues.append(_error("HRIS_ASSISTED_SOURCE_INVALID", "HRIS"))


def _validate_utilities(
    mapped: MappedModuleConfiguration,
    issues: list[ConfigImportIssue],
) -> None:
    rows = mapped.tables.get("attachment_consolidation_settings", ())
    if rows and int(rows[0]["txt_max_lines"]) <= 0:
        issues.append(_error("UTILITIES_TXT_MAX_LINES_INVALID", "UTILITIES"))


def _duplicates(
    values: list[object],
    code: str,
    module: str,
    issues: list[ConfigImportIssue],
) -> None:
    duplicates = [value for value, count in Counter(values).items() if count > 1]
    for value in duplicates:
        issues.append(_error(code, module, value=value))


def _error(
    code: str,
    module: str,
    *,
    field: str | None = None,
    value: object = None,
    message: str | None = None,
) -> ConfigImportIssue:
    return ConfigImportIssue(
        code=code,
        severity=IssueSeverity.ERROR,
        module=module,
        field=field,
        message=message or code.replace("_", " ").title(),
        current_value=value,
    )
