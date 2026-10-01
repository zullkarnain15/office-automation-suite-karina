"""Constants shared by the OAS-K SQLite foundation."""

from __future__ import annotations

SCHEMA_VERSION = 4
DEFAULT_BUSY_TIMEOUT_MS = 5_000
JOURNAL_MODE = "DELETE"
SYNCHRONOUS_MODE = "FULL"

REQUIRED_TABLES: tuple[str, ...] = (
    "database_metadata",
    "global_settings",
    "application_preferences",
    "attendance_settings",
    "attendance_sources",
    "outlook_settings",
    "outlook_sender_master",
    "outlook_subject_rules",
    "outlook_attachment_rules",
    "outlook_validation_rules",
    "outlook_reply_templates",
    "outlook_summary_recipients",
    "hris_settings",
    "hris_run_controls",
    "hris_assisted_steps",
    "comparison_settings",
    "attachment_consolidation_settings",
    "att_data_repair_settings",
    "job_history",
    "job_files",
    "job_status_events",
    "configuration_audit",
    "config_import_batches",
    "backup_history",
    "system_health_history",
)

REQUIRED_INDEXES: tuple[str, ...] = (
    "idx_attendance_sources_workflow_active",
    "idx_outlook_sender_email_active",
    "idx_outlook_sender_workflow_branch",
    "idx_outlook_subject_workflow_active",
    "idx_outlook_attachment_workflow_active",
    "idx_outlook_validation_workflow_active",
    "idx_outlook_reply_trigger_active",
    "idx_outlook_recipient_type_active",
    "idx_hris_run_controls_workflow_active",
    "idx_hris_assisted_steps_active_sequence",
    "idx_job_history_module_started",
    "idx_job_history_status_started",
    "idx_job_history_workflow_started",
    "idx_job_files_job",
    "idx_job_files_hash",
    "idx_job_status_events_job_time",
    "idx_configuration_audit_module_time",
    "idx_configuration_audit_batch",
    "idx_config_import_batches_module_time",
    "idx_config_import_batches_hash",
    "idx_backup_history_action_time",
    "idx_backup_history_hash",
    "idx_system_health_check_time",
)

UNIFIED_JOB_STATUSES: frozenset[str] = frozenset(
    {
        "PENDING",
        "VALIDATING",
        "READY_FOR_UPLOAD",
        "RUNNING",
        "PAUSED",
        "COMPLETED",
        "COMPLETED_WITH_WARNING",
        "FAILED",
        "CANCELLED",
        "NEED_REVIEW",
        "SKIPPED",
        "UPLOADED",
    }
)

AUDIT_CHANGE_SOURCES: frozenset[str] = frozenset(
    {
        "Unified UI",
        "Excel Import",
        "Migration",
        "Restore",
        "Reset Default",
    }
)
