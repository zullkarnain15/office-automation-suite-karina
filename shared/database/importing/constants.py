"""Workbook signatures and relational import contracts."""

from __future__ import annotations

from shared.database.importing.models import WorkbookIdentity

WORKBOOK_SIGNATURES: dict[WorkbookIdentity, frozenset[str]] = {
    WorkbookIdentity.ATTENDANCE_LEGACY: frozenset(
        {"General", "MDB_HO", "MDB_Branch", "Output", "Reference"}
    ),
    WorkbookIdentity.OUTLOOK_REVISI_LEGACY: frozenset(
        {
            "General",
            "HO_Sender_Master",
            "Branch_Sender_Master",
            "Subject_Rules",
            "Attachment_Rules",
            "Validation_Rules",
            "Reply_Templates",
        }
    ),
    WorkbookIdentity.HRIS_LEGACY: frozenset(
        {"General", "Run_Control", "Browser", "Upload", "Reference"}
    ),
    WorkbookIdentity.OAS_K_UNIFIED: frozenset(
        {
            "Guide",
            "Global_Settings",
            "Attendance_Settings",
            "Attendance_Sources",
            "Outlook_Settings",
            "Outlook_Subject_Rules",
            "Outlook_Attachment_Rules",
            "Outlook_Validation_Rules",
            "Outlook_Reply_Templates",
            "Outlook_Summary_Recipients",
            "HRIS_Settings",
            "HRIS_Run_Controls",
            "HRIS_Assisted_Steps",
            "Comparison_Settings",
            "Attachment_Consolidation",
        }
    ),
}

MODULE_TABLES: dict[str, tuple[str, ...]] = {
    "ATTENDANCE": ("attendance_settings", "attendance_sources"),
    "OUTLOOK_REVISI": (
        "outlook_settings",
        "outlook_sender_master",
        "outlook_subject_rules",
        "outlook_attachment_rules",
        "outlook_validation_rules",
        "outlook_reply_templates",
        "outlook_summary_recipients",
    ),
    "HRIS": ("hris_settings", "hris_run_controls", "hris_assisted_steps"),
    "UTILITIES": (
        "comparison_settings",
        "attachment_consolidation_settings",
    ),
    "GLOBAL": ("global_settings",),
}

TABLE_KEYS: dict[str, tuple[str, ...]] = {
    "global_settings": ("global_settings_id",),
    "attendance_settings": ("attendance_settings_id",),
    "attendance_sources": ("workflow", "source_code"),
    "outlook_settings": ("outlook_settings_id",),
    "outlook_sender_master": (
        "workflow",
        "company_code",
        "branch_code",
        "sender_email",
    ),
    "outlook_subject_rules": ("workflow", "subject_pattern"),
    "outlook_attachment_rules": ("workflow", "extension"),
    "outlook_validation_rules": ("rule_code", "workflow"),
    "outlook_reply_templates": ("reply_code",),
    "outlook_summary_recipients": ("recipient_type", "email_address"),
    "hris_settings": ("hris_settings_id",),
    "hris_run_controls": ("workflow", "run_control_id"),
    "hris_assisted_steps": ("step_name",),
    "comparison_settings": ("comparison_settings_id",),
    "attachment_consolidation_settings": ("attachment_settings_id",),
}

TABLE_PRIMARY_KEYS: dict[str, str] = {
    "attendance_sources": "attendance_source_id",
    "outlook_sender_master": "sender_id",
    "outlook_subject_rules": "subject_rule_id",
    "outlook_attachment_rules": "attachment_rule_id",
    "outlook_validation_rules": "validation_rule_id",
    "outlook_reply_templates": "reply_template_id",
    "outlook_summary_recipients": "recipient_id",
    "hris_run_controls": "run_control_pk",
    "hris_assisted_steps": "assisted_step_id",
}

UNIFIED_SHEET_TABLES: dict[str, tuple[str, str, str]] = {
    "Attendance_Sources": (
        "ATTENDANCE",
        "attendance_sources",
        "workflow",
    ),
    "Outlook_Sender_Master": (
        "OUTLOOK_REVISI",
        "outlook_sender_master",
        "workflow",
    ),
    "Outlook_HO_Senders": (
        "OUTLOOK_REVISI",
        "outlook_sender_master",
        "sender_email",
    ),
    "Outlook_Branch_Senders": (
        "OUTLOOK_REVISI",
        "outlook_sender_master",
        "sender_email",
    ),
    "Outlook_Subject_Rules": (
        "OUTLOOK_REVISI",
        "outlook_subject_rules",
        "workflow",
    ),
    "Outlook_Attachment_Rules": (
        "OUTLOOK_REVISI",
        "outlook_attachment_rules",
        "workflow",
    ),
    "Outlook_Validation_Rules": (
        "OUTLOOK_REVISI",
        "outlook_validation_rules",
        "rule_code",
    ),
    "Outlook_Reply_Templates": (
        "OUTLOOK_REVISI",
        "outlook_reply_templates",
        "reply_code",
    ),
    "Outlook_Summary_Recipients": (
        "OUTLOOK_REVISI",
        "outlook_summary_recipients",
        "recipient_type",
    ),
    "HRIS_Run_Controls": ("HRIS", "hris_run_controls", "workflow"),
    "HRIS_Assisted_Steps": (
        "HRIS",
        "hris_assisted_steps",
        "sequence",
    ),
}

# DB2B's operator-facing workbook stores singleton settings vertically.  The
# mapper still accepts the original horizontal DB2A contract via
# UNIFIED_HORIZONTAL_SETTING_SHEETS for backward compatibility.
UNIFIED_VERTICAL_SETTING_SHEETS: dict[str, tuple[str, str]] = {
    "Global_Settings": ("GLOBAL", "global_settings"),
    "Attendance_Settings": ("ATTENDANCE", "attendance_settings"),
    "Outlook_Settings": ("OUTLOOK_REVISI", "outlook_settings"),
    "HRIS_Settings": ("HRIS", "hris_settings"),
    "Comparison_Settings": ("UTILITIES", "comparison_settings"),
    "Attachment_Consolidation": (
        "UTILITIES",
        "attachment_consolidation_settings",
    ),
}

UNIFIED_HORIZONTAL_SETTING_SHEETS: dict[str, tuple[str, str, str]] = {
    "Global_Settings": ("GLOBAL", "global_settings", "output_root"),
    "Attendance_Settings": (
        "ATTENDANCE",
        "attendance_settings",
        "use_global_output",
    ),
    "Outlook_Settings": (
        "OUTLOOK_REVISI",
        "outlook_settings",
        "use_global_output",
    ),
    "HRIS_Settings": ("HRIS", "hris_settings", "use_global_output"),
    "Comparison_Settings": (
        "UTILITIES",
        "comparison_settings",
        "use_global_output",
    ),
    "Attachment_Consolidation": (
        "UTILITIES",
        "attachment_consolidation_settings",
        "use_global_output",
    ),
}

SINGLETON_IDS: dict[str, tuple[str, int]] = {
    "global_settings": ("global_settings_id", 1),
    "attendance_settings": ("attendance_settings_id", 1),
    "outlook_settings": ("outlook_settings_id", 1),
    "hris_settings": ("hris_settings_id", 1),
    "comparison_settings": ("comparison_settings_id", 1),
    "attachment_consolidation_settings": ("attachment_settings_id", 1),
}
