from __future__ import annotations

from pathlib import Path

from shared.database import SchemaManager, SQLiteConnectionFactory
from shared.database.repositories import GlobalSettingsRepository
from ui.configuration_ux_models import ActiveConfigurationStatus
from ui.services.module_configuration_service import ModuleConfigurationService


def configured_database(tmp_path: Path) -> Path:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "ui5b")
    with SQLiteConnectionFactory().connect(database) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(tmp_path / "output"),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.executescript(
            """
            INSERT INTO attendance_settings
                (attendance_settings_id, split_txt_rows, updated_at)
            VALUES (1, 10000, '2026-07-21T10:15:00');
            INSERT INTO attendance_sources
                (workflow, source_code, source_name, mdb_path, is_active,
                 sort_order, created_at, updated_at)
            VALUES
                ('HO', 'HO1', 'HO One', 'C:/fixture/ho.mdb', 1, 1, '2026-07-21', '2026-07-21'),
                ('BRANCH', 'B1', 'Branch One', 'C:/fixture/b.mdb', 1, 1, '2026-07-21', '2026-07-21');
            INSERT INTO outlook_settings
                (outlook_settings_id, mailbox_smtp, source_folder, send_mode,
                 auto_reply_enabled, payroll_period, updated_at)
            VALUES
                (1, 'karina.hr.1@oto.co.id', 'Inbox', 'DRAFT', 0,
                 '07-2026', '2026-07-21');
            INSERT INTO outlook_subject_rules
                (workflow, subject_pattern, is_active, created_at, updated_at)
            VALUES ('HO', 'Revisi', 1, '2026-07-21', '2026-07-21');
            INSERT INTO outlook_sender_master
                (workflow, sender_email, is_active, created_at, updated_at)
            VALUES ('HO', 'sender@example.test', 1, '2026-07-21', '2026-07-21');
            INSERT INTO outlook_attachment_rules
                (workflow, extension, is_active, created_at, updated_at)
            VALUES ('HO', '.xlsx', 1, '2026-07-21', '2026-07-21');
            INSERT INTO outlook_validation_rules
                (rule_code, workflow, rule_value, is_active, created_at, updated_at)
            VALUES ('ROW', 'HO', '1', 1, '2026-07-21', '2026-07-21');
            INSERT INTO outlook_reply_templates
                (reply_code, recipient_type, trigger_code, body_template, is_active,
                 created_at, updated_at)
            VALUES ('SUCCESS', 'SENDER', 'SUCCESS', 'Line 1\nLine 2', 1,
                    '2026-07-21', '2026-07-21');
            INSERT INTO outlook_summary_recipients
                (recipient_type, email_address, is_active, created_at, updated_at)
            VALUES ('TO', 'pic@example.test', 1, '2026-07-21', '2026-07-21');
            INSERT INTO hris_settings
                (hris_settings_id, hris_url, verification_success_texts,
                 verification_failure_texts, updated_at)
            VALUES (1, 'https://hris.example.test', 'success', 'failed', '2026-07-21');
            INSERT INTO hris_run_controls
                (workflow, sequence, run_control_id, is_active, created_at, updated_at)
            VALUES ('HO', 1, '001', 1, '2026-07-21', '2026-07-21');
            INSERT INTO hris_assisted_steps
                (sequence, step_name, action, input_source, method, is_active,
                 created_at, updated_at)
            VALUES (1, 'Open', 'manual_continue', 'NONE', 'manual', 1,
                    '2026-07-21', '2026-07-21');
            INSERT INTO comparison_settings
                (comparison_settings_id, updated_at)
            VALUES (1, '2026-07-21');
            INSERT INTO attachment_consolidation_settings
                (attachment_settings_id, txt_max_lines, updated_at)
            VALUES (1, 10000, '2026-07-21');
            """
        )
    return database


def test_four_module_summaries_are_read_from_sqlite(tmp_path: Path) -> None:
    database = configured_database(tmp_path)
    summaries = ModuleConfigurationService().load_summaries(database)

    assert [item.module for item in summaries] == [
        "ATTENDANCE",
        "OUTLOOK_REVISI",
        "HRIS",
        "UTILITIES",
    ]
    attendance, outlook, hris, utilities = summaries
    assert attendance.status == ActiveConfigurationStatus.ACTIVE
    assert ("HO Sources", "1 aktif") in attendance.fields
    assert ("Mailbox", "karina.hr.1@oto.co.id") in outlook.fields
    assert ("Payroll Period", "07-2026") in outlook.fields
    assert outlook.status == ActiveConfigurationStatus.ACTIVE
    assert ("HO Run Controls", "1 aktif") in hris.fields
    assert ("TXT Max Lines", "10000") in utilities.fields


def test_missing_database_is_read_only_and_reports_unavailable(tmp_path: Path) -> None:
    database = tmp_path / "missing" / "OAS-K.db"
    summaries = ModuleConfigurationService().load_summaries(database)
    assert all(item.status == ActiveConfigurationStatus.UNAVAILABLE for item in summaries)
    assert not database.exists() and not database.parent.exists()


def test_details_are_read_only_and_cover_each_module(tmp_path: Path) -> None:
    database = configured_database(tmp_path)
    service = ModuleConfigurationService()
    before = database.read_bytes()
    details = {
        module: service.load_detail(database, module)
        for module in ("ATTENDANCE", "OUTLOOK_REVISI", "HRIS", "UTILITIES")
    }
    assert details["ATTENDANCE"].sections[1][0] == "Sumber Aktif"
    assert any(label == "Recipients" for label, _ in details["OUTLOOK_REVISI"].sections)
    assert any(label == "Assisted Steps" for label, _ in details["HRIS"].sections)
    assert len(details["UTILITIES"].sections) == 2
    assert database.read_bytes() == before
