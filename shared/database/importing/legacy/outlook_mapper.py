"""Map the audited Outlook Revisi legacy workbook to schema-v1 rows."""

from __future__ import annotations

from typing import Any

from shared.database.importing.legacy.common import (
    key_value_rows,
    split_values,
    table_rows,
    value_of,
)
from shared.database.importing.models import (
    ConfigImportIssue,
    IssueSeverity,
    MappedModuleConfiguration,
    WorkbookData,
)
from shared.database.importing.normalizer import (
    is_development_path,
    is_gmail_test_address,
    normalize_boolean,
    normalize_path,
    normalize_workflow,
)
from shared.database.time_utils import current_timestamp
from shared.payroll_period import normalize_payroll_period


def map_outlook(workbook: WorkbookData) -> MappedModuleConfiguration:
    issues: list[ConfigImportIssue] = []
    timestamp = current_timestamp()
    general = key_value_rows(workbook.sheets["General"])

    auto_reply = normalize_boolean(
        value_of(general, "Auto_Reply_Enabled", "FALSE")
    )
    send_mode = str(value_of(general, "Send_Mode", "DRAFT")).strip().upper()
    if auto_reply and send_mode == "SEND":
        issues.append(
            ConfigImportIssue(
                code="OUTLOOK_AUTOMATIC_SEND_ENABLED",
                severity=IssueSeverity.CRITICAL,
                module="OUTLOOK_REVISI",
                sheet="General",
                field="Auto_Reply_Enabled/Send_Mode",
                message=(
                    "Automatic reply and live SEND mode are both enabled."
                ),
                proposed_value="Auto_Reply=1; Send_Mode=SEND",
                confirmation_required=True,
            )
        )

    settings = {
        "outlook_settings_id": 1,
        "use_global_output": 1,
        "use_global_period": 1,
        "integration_method": str(
            value_of(general, "Integration_Method", "OOM_COM")
        ).strip(),
        "mailbox_smtp": str(value_of(general, "Mailbox_SMTP", "")).strip(),
        "source_folder": str(
            value_of(general, "Source_Folder", "Inbox")
        ).strip(),
        "reply_from_smtp": _optional(value_of(general, "Reply_From_SMTP")),
        "send_transport": str(
            value_of(general, "Send_Transport", "OUTLOOK")
        ).strip().upper(),
        "smtp_server": _optional(value_of(general, "SMTP_Server")),
        "smtp_port": int(value_of(general, "SMTP_Port", 25)),
        "smtp_timeout_seconds": int(
            value_of(general, "SMTP_Timeout_Seconds", 30)
        ),
        "save_smtp_copy_to_sent": normalize_boolean(
            value_of(general, "Save_SMTP_Copy_To_Sent", "TRUE")
        ),
        "processed_folder": str(
            value_of(general, "Processed_Folder", "Deleted Items")
        ).strip(),
        "auto_reply_enabled": auto_reply,
        "send_mode": send_mode,
        "resubmit_deadline": _optional(
            value_of(general, "Resubmit_Deadline")
        ),
        "txt_max_lines": int(value_of(general, "TXT_Max_Lines", 10000)),
        "module_display_name": str(
            value_of(general, "Module_Display_Name", "Outlook Revisi")
        ).strip(),
        "payroll_period": normalize_payroll_period(
            value_of(general, "Payroll_Period"),
            allow_blank=True,
        ),
        "updated_at": timestamp,
    }

    candidates: dict[str, Any] = {}
    output_root = value_of(general, "Output_Root")
    if output_root:
        candidates["output_root"] = normalize_path(output_root)
        if is_development_path(candidates["output_root"]):
            issues.append(
                ConfigImportIssue(
                    code="DEVELOPMENT_PATH_DETECTED",
                    severity=IssueSeverity.WARNING,
                    module="OUTLOOK_REVISI",
                    sheet="General",
                    field="Output_Root",
                    message="Outlook output root appears project-local.",
                    proposed_value=candidates["output_root"],
                    confirmation_required=True,
                )
            )
    senders: list[dict[str, Any]] = []
    for workflow, sheet_name in (
        ("HO", "HO_Sender_Master"),
        ("BRANCH", "Branch_Sender_Master"),
    ):
        for record in table_rows(
            workbook.sheets[sheet_name],
            required_header="Active",
        ):
            active = normalize_boolean(record["Active"].value)
            email_cell = record.get("Sender_Email")
            email = (
                str(email_cell.value).strip()
                if email_cell is not None and email_cell.value
                else ""
            )
            if not email:
                if active:
                    issues.append(
                        ConfigImportIssue(
                            code="ACTIVE_SENDER_EMAIL_MISSING",
                            severity=IssueSeverity.ERROR,
                            module="OUTLOOK_REVISI",
                            sheet=sheet_name,
                            row_number=record["Active"].row_number,
                            field="Sender_Email",
                            message="Active sender row has no email address.",
                        )
                    )
                continue
            sender = {
                "workflow": workflow,
                "company_code": _cell_text(record.get("Company")),
                "branch_code": _cell_text(record.get("Branch_Code")),
                "sender_nik": _optional(_cell_value(record.get("Nik_Sender"))),
                "sender_name": _optional(
                    _cell_value(record.get("Sender_Name"))
                ),
                "sender_email": email,
                "supervisor_nik": _optional(
                    _cell_value(record.get("Nik_Spv"))
                ),
                "supervisor_name": _optional(
                    _cell_value(record.get("Name_SPV"))
                ),
                "required_cc_email": _optional(
                    _cell_value(record.get("Required_CC_Email"))
                ),
                "is_active": active,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            senders.append(sender)
            for field in ("sender_email", "required_cc_email"):
                value = sender[field]
                if value and is_gmail_test_address(value):
                    issues.append(
                        ConfigImportIssue(
                            code="TEST_SENDER_DETECTED",
                            severity=IssueSeverity.WARNING,
                            module="OUTLOOK_REVISI",
                            sheet=sheet_name,
                            row_number=email_cell.row_number,
                            field=field,
                            message="Gmail test address detected.",
                            proposed_value=value,
                            confirmation_required=bool(active),
                        )
                    )

    subject_rules = [
        {
            "workflow": normalize_workflow(row["Workflow"].value),
            "subject_pattern": str(row["Subject_Pattern"].value),
            "is_active": normalize_boolean(row["Active"].value),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for row in table_rows(
            workbook.sheets["Subject_Rules"],
            required_header="Active",
        )
        if row.get("Subject_Pattern") is not None
        and row["Subject_Pattern"].value
    ]

    attachment_rules: list[dict[str, Any]] = []
    for row in table_rows(
        workbook.sheets["Attachment_Rules"],
        required_header="Active",
    ):
        if row.get("Allowed_Extensions") is None:
            continue
        for extension in split_values(row["Allowed_Extensions"].value):
            attachment_rules.append(
                {
                    "workflow": normalize_workflow(row["Workflow"].value),
                    "extension": extension.lower(),
                    "is_active": normalize_boolean(row["Active"].value),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )

    validation_rules = [
        {
            "rule_code": str(row["Rule_Code"].value).strip(),
            "workflow": normalize_workflow(
                row["Workflow"].value,
                allow_all=True,
            ),
            "rule_value": str(row["Rule_Value"].value),
            "is_active": normalize_boolean(row["Active"].value),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for row in table_rows(
            workbook.sheets["Validation_Rules"],
            required_header="Active",
        )
        if row.get("Rule_Code") is not None and row["Rule_Code"].value
    ]

    reply_templates = [
        {
            "reply_code": str(row["Reply_Code"].value).strip(),
            "recipient_type": str(row["Recipient_Type"].value).strip().upper(),
            "trigger_code": str(row["Trigger"].value).strip(),
            "subject_template": _optional(row["Subject_Template"].value),
            "body_template": str(row["Body_Template"].value).replace(
                "\r\n", "\n"
            ),
            "is_active": normalize_boolean(row["Active"].value),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for row in table_rows(
            workbook.sheets["Reply_Templates"],
            required_header="Active",
        )
        if row.get("Reply_Code") is not None and row["Reply_Code"].value
    ]

    recipients = []
    for recipient_type, key in (
        ("TO", "PIC_HR_Emails"),
        ("CC", "SPV_PIC_HR_Emails"),
    ):
        for order, email in enumerate(
            split_values(value_of(general, key)),
            start=1,
        ):
            recipients.append(
                {
                    "recipient_type": recipient_type,
                    "email_address": email,
                    "is_active": 1,
                    "sort_order": order,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )

    return MappedModuleConfiguration(
        module="OUTLOOK_REVISI",
        tables={
            "outlook_settings": (settings,),
            "outlook_sender_master": tuple(senders),
            "outlook_subject_rules": tuple(subject_rules),
            "outlook_attachment_rules": tuple(attachment_rules),
            "outlook_validation_rules": tuple(validation_rules),
            "outlook_reply_templates": tuple(reply_templates),
            "outlook_summary_recipients": tuple(recipients),
        },
        global_candidates=candidates,
        source_file=workbook.detection.path,
        source_hash=workbook.detection.sha256,
        issues=tuple(issues),
    )


def _optional(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value)


def _cell_value(cell: Any) -> Any:
    return cell.value if cell is not None else None


def _cell_text(cell: Any) -> str:
    value = _cell_value(cell)
    return "" if value is None else str(value).strip()
