-- OAS-K SQLite schema version 1.
-- Metadata is inserted by SchemaManager in the same initialization transaction.

CREATE TABLE database_metadata (
    metadata_id INTEGER PRIMARY KEY CHECK (metadata_id = 1),
    database_uuid TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL CHECK (schema_version > 0),
    application_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_migrated_at TEXT
);

CREATE TABLE global_settings (
    global_settings_id INTEGER PRIMARY KEY CHECK (global_settings_id = 1),
    output_root TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    CHECK (
        (period_start IS NULL AND period_end IS NULL)
        OR (
            period_start IS NOT NULL
            AND period_end IS NOT NULL
            AND period_start <= period_end
        )
    )
);

CREATE TABLE application_preferences (
    preference_key TEXT PRIMARY KEY,
    preference_value TEXT NOT NULL,
    value_type TEXT NOT NULL
        CHECK (value_type IN ('TEXT', 'INTEGER', 'REAL', 'BOOLEAN')),
    updated_at TEXT NOT NULL
);

CREATE TABLE attendance_settings (
    attendance_settings_id INTEGER PRIMARY KEY
        CHECK (attendance_settings_id = 1),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    use_global_period INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_period IN (0, 1)),
    split_txt_rows INTEGER NOT NULL DEFAULT 10000
        CHECK (split_txt_rows > 0),
    generate_report_default INTEGER NOT NULL DEFAULT 1
        CHECK (generate_report_default IN (0, 1)),
    default_workflow TEXT NOT NULL DEFAULT 'HO'
        CHECK (default_workflow IN ('HO', 'BRANCH')),
    updated_at TEXT NOT NULL
);

CREATE TABLE attendance_sources (
    attendance_source_id INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH')),
    source_code TEXT NOT NULL,
    source_name TEXT NOT NULL,
    mdb_path TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workflow, source_code),
    CHECK (
        is_active = 0
        OR (mdb_path IS NOT NULL AND length(trim(mdb_path)) > 0)
    )
);

CREATE INDEX idx_attendance_sources_workflow_active
    ON attendance_sources (workflow, is_active, sort_order);

CREATE TABLE outlook_settings (
    outlook_settings_id INTEGER PRIMARY KEY CHECK (outlook_settings_id = 1),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    use_global_period INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_period IN (0, 1)),
    integration_method TEXT NOT NULL DEFAULT 'OOM_COM'
        CHECK (integration_method = 'OOM_COM'),
    mailbox_smtp TEXT NOT NULL,
    source_folder TEXT NOT NULL DEFAULT 'Inbox',
    reply_from_smtp TEXT,
    send_transport TEXT NOT NULL DEFAULT 'OUTLOOK'
        CHECK (send_transport IN ('OUTLOOK', 'SMTP')),
    smtp_server TEXT,
    smtp_port INTEGER NOT NULL DEFAULT 25
        CHECK (smtp_port BETWEEN 1 AND 65535),
    smtp_timeout_seconds INTEGER NOT NULL DEFAULT 30
        CHECK (smtp_timeout_seconds > 0),
    save_smtp_copy_to_sent INTEGER NOT NULL DEFAULT 1
        CHECK (save_smtp_copy_to_sent IN (0, 1)),
    processed_folder TEXT NOT NULL DEFAULT 'Deleted Items',
    auto_reply_enabled INTEGER NOT NULL DEFAULT 0
        CHECK (auto_reply_enabled IN (0, 1)),
    send_mode TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (send_mode IN ('SEND', 'DRAFT')),
    resubmit_deadline TEXT,
    txt_max_lines INTEGER NOT NULL DEFAULT 10000
        CHECK (txt_max_lines > 0),
    module_display_name TEXT NOT NULL DEFAULT 'Outlook Revisi',
    updated_at TEXT NOT NULL,
    CHECK (
        send_transport != 'SMTP'
        OR (
            smtp_server IS NOT NULL
            AND length(trim(smtp_server)) > 0
            AND reply_from_smtp IS NOT NULL
            AND length(trim(reply_from_smtp)) > 0
        )
    ),
    CHECK (send_transport != 'SMTP' OR send_mode != 'DRAFT')
);

CREATE TABLE outlook_sender_master (
    sender_id INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH')),
    company_code TEXT NOT NULL DEFAULT '',
    branch_code TEXT NOT NULL DEFAULT '',
    sender_nik TEXT,
    sender_name TEXT,
    sender_email TEXT NOT NULL COLLATE NOCASE,
    supervisor_nik TEXT,
    supervisor_name TEXT,
    required_cc_email TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workflow, company_code, branch_code, sender_email),
    CHECK (
        workflow != 'BRANCH'
        OR (
            length(trim(company_code)) > 0
            AND length(trim(branch_code)) > 0
        )
    )
);

CREATE INDEX idx_outlook_sender_email_active
    ON outlook_sender_master (sender_email, is_active);

CREATE INDEX idx_outlook_sender_workflow_branch
    ON outlook_sender_master (workflow, company_code, branch_code);

CREATE TABLE outlook_subject_rules (
    subject_rule_id INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH')),
    subject_pattern TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workflow, subject_pattern)
);

CREATE INDEX idx_outlook_subject_workflow_active
    ON outlook_subject_rules (workflow, is_active);

CREATE TABLE outlook_attachment_rules (
    attachment_rule_id INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH')),
    extension TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workflow, extension),
    CHECK (substr(extension, 1, 1) = '.')
);

CREATE INDEX idx_outlook_attachment_workflow_active
    ON outlook_attachment_rules (workflow, is_active);

CREATE TABLE outlook_validation_rules (
    validation_rule_id INTEGER PRIMARY KEY,
    rule_code TEXT NOT NULL,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH', 'ALL')),
    rule_value TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (rule_code, workflow)
);

CREATE INDEX idx_outlook_validation_workflow_active
    ON outlook_validation_rules (workflow, is_active);

CREATE TABLE outlook_reply_templates (
    reply_template_id INTEGER PRIMARY KEY,
    reply_code TEXT NOT NULL UNIQUE,
    recipient_type TEXT NOT NULL CHECK (recipient_type IN ('SENDER', 'PIC_HR')),
    trigger_code TEXT NOT NULL,
    subject_template TEXT,
    body_template TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_outlook_reply_trigger_active
    ON outlook_reply_templates (trigger_code, is_active);

CREATE TABLE outlook_summary_recipients (
    recipient_id INTEGER PRIMARY KEY,
    recipient_type TEXT NOT NULL CHECK (recipient_type IN ('TO', 'CC')),
    email_address TEXT NOT NULL COLLATE NOCASE,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (recipient_type, email_address)
);

CREATE INDEX idx_outlook_recipient_type_active
    ON outlook_summary_recipients (recipient_type, is_active, sort_order);

CREATE TABLE hris_settings (
    hris_settings_id INTEGER PRIMARY KEY CHECK (hris_settings_id = 1),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    use_global_period INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_period IN (0, 1)),
    hris_url TEXT NOT NULL,
    browser_channel TEXT NOT NULL DEFAULT 'msedge',
    browser_headless INTEGER NOT NULL DEFAULT 0
        CHECK (browser_headless IN (0, 1)),
    stop_on_first_failure INTEGER NOT NULL DEFAULT 1
        CHECK (stop_on_first_failure IN (0, 1)),
    click_profile_path TEXT,
    manual_recovery_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (manual_recovery_enabled IN (0, 1)),
    require_profile_match INTEGER NOT NULL DEFAULT 1
        CHECK (require_profile_match IN (0, 1)),
    browser_x INTEGER NOT NULL DEFAULT 0,
    browser_y INTEGER NOT NULL DEFAULT 0,
    browser_width INTEGER NOT NULL DEFAULT 1200 CHECK (browser_width >= 640),
    browser_height INTEGER NOT NULL DEFAULT 800 CHECK (browser_height >= 480),
    browser_zoom INTEGER NOT NULL DEFAULT 100 CHECK (browser_zoom > 0),
    verification_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (verification_enabled IN (0, 1)),
    verification_wait_seconds REAL NOT NULL DEFAULT 1
        CHECK (verification_wait_seconds >= 0),
    verification_timeout_seconds REAL NOT NULL DEFAULT 10
        CHECK (verification_timeout_seconds >= verification_wait_seconds),
    verification_poll_seconds REAL NOT NULL DEFAULT 1
        CHECK (verification_poll_seconds > 0),
    verification_success_texts TEXT NOT NULL,
    verification_failure_texts TEXT NOT NULL,
    manual_verification_on_unknown INTEGER NOT NULL DEFAULT 1
        CHECK (manual_verification_on_unknown IN (0, 1)),
    manual_verification_on_error INTEGER NOT NULL DEFAULT 1
        CHECK (manual_verification_on_error IN (0, 1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE hris_run_controls (
    run_control_pk INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL CHECK (workflow IN ('HO', 'BRANCH')),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    run_control_id TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workflow, sequence),
    UNIQUE (workflow, run_control_id)
);

CREATE INDEX idx_hris_run_controls_workflow_active
    ON hris_run_controls (workflow, is_active, sequence);

CREATE TABLE hris_assisted_steps (
    assisted_step_id INTEGER PRIMARY KEY,
    sequence INTEGER NOT NULL UNIQUE CHECK (sequence > 0),
    step_name TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL CHECK (
        action IN (
            'click',
            'click_type',
            'type',
            'press',
            'attach_file',
            'wait',
            'manual_continue'
        )
    ),
    input_source TEXT NOT NULL CHECK (
        input_source IN (
            'NONE',
            'RUN_CONTROL_ID',
            'START_DATE',
            'END_DATE',
            'TXT_FILE_PATH'
        )
    ),
    method TEXT NOT NULL CHECK (
        method IN ('coordinate', 'playwright', 'manual', 'assisted')
    ),
    is_required INTEGER NOT NULL DEFAULT 0 CHECK (is_required IN (0, 1)),
    wait_after_seconds REAL NOT NULL DEFAULT 0 CHECK (wait_after_seconds >= 0),
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_hris_assisted_steps_active_sequence
    ON hris_assisted_steps (is_active, sequence);

CREATE TABLE comparison_settings (
    comparison_settings_id INTEGER PRIMARY KEY
        CHECK (comparison_settings_id = 1),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    use_global_period INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_period IN (0, 1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE attachment_consolidation_settings (
    attachment_settings_id INTEGER PRIMARY KEY
        CHECK (attachment_settings_id = 1),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    txt_max_lines INTEGER NOT NULL DEFAULT 10000 CHECK (txt_max_lines > 0),
    updated_at TEXT NOT NULL
);

CREATE TABLE job_history (
    job_pk INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL,
    module_code TEXT NOT NULL,
    feature_code TEXT,
    workflow TEXT CHECK (workflow IS NULL OR workflow IN ('HO', 'BRANCH')),
    legacy_status TEXT,
    unified_status TEXT NOT NULL CHECK (
        unified_status IN (
            'PENDING',
            'VALIDATING',
            'READY_FOR_UPLOAD',
            'RUNNING',
            'PAUSED',
            'COMPLETED',
            'COMPLETED_WITH_WARNING',
            'FAILED',
            'CANCELLED',
            'NEED_REVIEW',
            'SKIPPED',
            'UPLOADED'
        )
    ),
    started_at TEXT,
    finished_at TEXT,
    duration_seconds REAL CHECK (
        duration_seconds IS NULL OR duration_seconds >= 0
    ),
    output_path_used TEXT NOT NULL,
    period_start_used TEXT,
    period_end_used TEXT,
    used_global_output INTEGER NOT NULL CHECK (used_global_output IN (0, 1)),
    used_global_period INTEGER NOT NULL CHECK (used_global_period IN (0, 1)),
    source_summary TEXT,
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    skipped_count INTEGER NOT NULL DEFAULT 0 CHECK (skipped_count >= 0),
    summary_json_path TEXT,
    process_log_path TEXT,
    error_message TEXT,
    configuration_snapshot_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (module_code, job_id),
    CHECK (
        (period_start_used IS NULL AND period_end_used IS NULL)
        OR (
            period_start_used IS NOT NULL
            AND period_end_used IS NOT NULL
            AND period_start_used <= period_end_used
        )
    )
);

CREATE INDEX idx_job_history_module_started
    ON job_history (module_code, started_at DESC);

CREATE INDEX idx_job_history_status_started
    ON job_history (unified_status, started_at DESC);

CREATE INDEX idx_job_history_workflow_started
    ON job_history (workflow, started_at DESC);

CREATE TABLE job_files (
    job_file_id INTEGER PRIMARY KEY,
    job_pk INTEGER NOT NULL,
    file_role TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER CHECK (file_size IS NULL OR file_size >= 0),
    file_hash TEXT,
    exists_at_last_check INTEGER NOT NULL DEFAULT 1
        CHECK (exists_at_last_check IN (0, 1)),
    recorded_at TEXT NOT NULL,
    last_checked_at TEXT,
    FOREIGN KEY (job_pk) REFERENCES job_history (job_pk)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    UNIQUE (job_pk, file_role, file_path)
);

CREATE INDEX idx_job_files_job ON job_files (job_pk);
CREATE INDEX idx_job_files_hash ON job_files (file_hash);

CREATE TABLE job_status_events (
    status_event_id INTEGER PRIMARY KEY,
    job_pk INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    legacy_status TEXT,
    unified_status TEXT NOT NULL CHECK (
        unified_status IN (
            'PENDING',
            'VALIDATING',
            'READY_FOR_UPLOAD',
            'RUNNING',
            'PAUSED',
            'COMPLETED',
            'COMPLETED_WITH_WARNING',
            'FAILED',
            'CANCELLED',
            'NEED_REVIEW',
            'SKIPPED',
            'UPLOADED'
        )
    ),
    phase TEXT,
    message TEXT,
    FOREIGN KEY (job_pk) REFERENCES job_history (job_pk)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX idx_job_status_events_job_time
    ON job_status_events (job_pk, occurred_at);

CREATE TABLE config_import_batches (
    import_batch_id INTEGER PRIMARY KEY,
    module_code TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    import_mode TEXT NOT NULL CHECK (
        import_mode IN (
            'Replace Module Configuration',
            'Merge Reference/Master Data'
        )
    ),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    rows_valid INTEGER NOT NULL DEFAULT 0 CHECK (rows_valid >= 0),
    rows_rejected INTEGER NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    error_summary TEXT,
    diagnostic_report_path TEXT,
    operator TEXT
);

CREATE INDEX idx_config_import_batches_module_time
    ON config_import_batches (module_code, started_at DESC);

CREATE INDEX idx_config_import_batches_hash
    ON config_import_batches (source_file_hash);

CREATE TABLE configuration_audit (
    audit_id INTEGER PRIMARY KEY,
    changed_at TEXT NOT NULL,
    module_code TEXT NOT NULL,
    setting_scope TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    change_source TEXT NOT NULL CHECK (
        change_source IN (
            'Unified UI',
            'Excel Import',
            'Migration',
            'Restore',
            'Reset Default'
        )
    ),
    operator TEXT,
    import_batch_id INTEGER,
    FOREIGN KEY (import_batch_id)
        REFERENCES config_import_batches (import_batch_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX idx_configuration_audit_module_time
    ON configuration_audit (module_code, changed_at DESC);

CREATE INDEX idx_configuration_audit_batch
    ON configuration_audit (import_batch_id);

CREATE TABLE backup_history (
    backup_id INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'BACKUP',
            'RESTORE_FROM_BACKUP',
            'IMPORT_EXISTING_DATABASE',
            'RESET_TO_DEFAULT'
        )
    ),
    source_path TEXT NOT NULL,
    backup_path TEXT,
    database_hash TEXT,
    schema_version INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    validation_result TEXT,
    operator TEXT,
    notes TEXT
);

CREATE INDEX idx_backup_history_action_time
    ON backup_history (action_type, started_at DESC);

CREATE INDEX idx_backup_history_hash
    ON backup_history (database_hash);

CREATE TABLE system_health_history (
    health_check_id INTEGER PRIMARY KEY,
    checked_at TEXT NOT NULL,
    check_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'WARNING', 'FAIL')),
    message TEXT NOT NULL,
    details_json TEXT
);

CREATE INDEX idx_system_health_check_time
    ON system_health_history (check_code, checked_at DESC);
