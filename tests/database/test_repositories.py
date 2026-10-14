"""Typed repository and transaction tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory
from shared.database.models import (
    BackupHistoryRecord,
    ConfigurationAuditRecord,
    JobFileRecord,
    JobHistoryRecord,
)
from shared.database.repositories import (
    AuditRepository,
    BackupHistoryRepository,
    GlobalSettingsRepository,
    JobRepository,
)


def test_global_settings_round_trip(database_path: Path) -> None:
    output = str(database_path.parent / "output")
    with SQLiteConnectionFactory().connect(database_path) as connection:
        repository = GlobalSettingsRepository(connection)
        saved = repository.save_global_settings(
            output_root=output,
            period_start="2026-07-01",
            period_end="2026-07-31",
            updated_by="tester",
        )
        loaded = repository.get_global_settings()

    assert loaded == saved
    assert loaded is not None
    assert loaded.output_root == output
    assert not Path(output).exists()


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-08-01", "2026-07-01"),
        ("20-07-2026", "2026-07-31"),
        ("2026-07-01", None),
    ],
)
def test_invalid_global_period_is_rejected(
    database_path: Path,
    start: str | None,
    end: str | None,
) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        repository = GlobalSettingsRepository(connection)
        with pytest.raises(ValueError):
            repository.save_global_settings(
                output_root="D:/Output",
                period_start=start,
                period_end=end,
            )
        assert repository.get_global_settings() is None


def test_job_lifecycle_and_file_reference(database_path: Path) -> None:
    factory = SQLiteConnectionFactory()
    with factory.connect(database_path) as connection:
        repository = JobRepository(connection)
        job_pk = repository.create_job(
            JobHistoryRecord(
                job_id="JOB-001",
                module_code="ATTENDANCE",
                feature_code=None,
                workflow="HO",
                legacy_status="READY",
                unified_status="PENDING",
                started_at="2026-07-20T10:00:00",
                output_path_used="D:/Output",
                period_start_used="2026-07-01",
                period_end_used="2026-07-31",
                used_global_output=True,
                used_global_period=False,
                created_at="2026-07-20T10:00:00",
            )
        )
        repository.update_job_status(
            module_code="ATTENDANCE",
            job_id="JOB-001",
            unified_status="RUNNING",
            legacy_status="RUNNING",
            occurred_at="2026-07-20T10:01:00",
        )
        file_pk = repository.add_job_file(
            JobFileRecord(
                job_pk=job_pk,
                file_role="PROCESS_LOG",
                file_path="D:/Output/Process.log",
                file_size=100,
                file_hash="abc123",
                recorded_at="2026-07-20T10:02:00",
            )
        )
        repository.finish_job(
            module_code="ATTENDANCE",
            job_id="JOB-001",
            unified_status="COMPLETED",
            finished_at="2026-07-20T10:05:00",
            duration_seconds=300,
            success_count=1,
        )
        loaded = repository.get_job_by_id(
            module_code="ATTENDANCE",
            job_id="JOB-001",
        )
        recent = repository.list_recent_jobs(limit=10)
        event_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM job_status_events
            WHERE job_pk = ?
            """,
            (job_pk,),
        ).fetchone()[0]

    assert job_pk > 0
    assert file_pk > 0
    assert loaded is not None
    assert loaded.unified_status == "COMPLETED"
    assert loaded.used_global_output is True
    assert loaded.used_global_period is False
    assert recent == [loaded]
    assert event_count == 3


def test_job_rejects_unknown_unified_status(
    database_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        repository = JobRepository(connection)
        with pytest.raises(ValueError, match="Unsupported"):
            repository.create_job(
                JobHistoryRecord(
                    job_id="BAD",
                    module_code="TEST",
                    unified_status="ENGINE_STATUS",
                    output_path_used="D:/Output",
                    used_global_output=True,
                    used_global_period=False,
                    created_at="2026-07-20T10:00:00",
                )
            )


def test_configuration_audit_can_be_stored(
    database_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        audit_id = AuditRepository(connection).add_audit_record(
            ConfigurationAuditRecord(
                changed_at="2026-07-20T10:00:00",
                module_code="GLOBAL",
                setting_scope="global_settings",
                setting_key="output_root",
                old_value=None,
                new_value="D:/Output",
                change_source="Unified UI",
                operator="tester",
            )
        )
        row = connection.execute(
            """
            SELECT setting_key, change_source
            FROM configuration_audit
            WHERE audit_id = ?
            """,
            (audit_id,),
        ).fetchone()

    assert tuple(row) == ("output_root", "Unified UI")


def test_backup_history_can_be_stored(database_path: Path) -> None:
    with SQLiteConnectionFactory().connect(database_path) as connection:
        backup_id = BackupHistoryRepository(
            connection
        ).add_backup_history(
            BackupHistoryRecord(
                action_type="BACKUP",
                source_path=str(database_path),
                backup_path=str(database_path.with_suffix(".backup.db")),
                schema_version=1,
                started_at="2026-07-20T10:00:00",
                finished_at="2026-07-20T10:00:01",
                status="COMPLETED",
                validation_result="PASS",
            )
        )
    assert backup_id > 0


def test_connection_context_rolls_back_multi_step_write(
    database_path: Path,
) -> None:
    factory = SQLiteConnectionFactory()
    with pytest.raises(RuntimeError, match="force rollback"):
        with factory.connect(database_path) as connection:
            GlobalSettingsRepository(connection).save_global_settings(
                output_root="D:/MustRollback",
                period_start="2026-07-01",
                period_end="2026-07-31",
            )
            AuditRepository(connection).add_audit_record(
                ConfigurationAuditRecord(
                    changed_at="2026-07-20T10:00:00",
                    module_code="GLOBAL",
                    setting_scope="global_settings",
                    setting_key="output_root",
                    old_value=None,
                    new_value="D:/MustRollback",
                    change_source="Unified UI",
                )
            )
            raise RuntimeError("force rollback")

    with factory.connect(database_path, read_only=True) as connection:
        settings_count = connection.execute(
            "SELECT COUNT(*) FROM global_settings"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM configuration_audit"
        ).fetchone()[0]
    assert settings_count == 0
    assert audit_count == 0


def test_hris_text_ids_and_multiline_template_round_trip(
    database_path: Path,
) -> None:
    timestamp = "2026-07-20T10:00:00"
    body = "Baris pertama\nBaris kedua {PAYROLL_PERIOD}\nSalam"
    with SQLiteConnectionFactory().connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO hris_run_controls (
                workflow,
                sequence,
                run_control_id,
                description,
                is_active,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            [
                ("HO", 1, "001", "First", timestamp, timestamp),
                ("HO", 2, "02", "Second", timestamp, timestamp),
            ],
        )
        connection.execute(
            """
            INSERT INTO outlook_reply_templates (
                reply_code,
                recipient_type,
                trigger_code,
                subject_template,
                body_template,
                is_active,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                "TEST_TEMPLATE",
                "SENDER",
                "TEST",
                "Subject {PAYROLL_PERIOD}",
                body,
                timestamp,
                timestamp,
            ),
        )

    with SQLiteConnectionFactory().connect(
        database_path,
        read_only=True,
    ) as connection:
        identifiers = [
            row[0]
            for row in connection.execute(
                """
                SELECT run_control_id
                FROM hris_run_controls
                ORDER BY sequence
                """
            ).fetchall()
        ]
        stored_body = connection.execute(
            """
            SELECT body_template
            FROM outlook_reply_templates
            WHERE reply_code = ?
            """,
            ("TEST_TEMPLATE",),
        ).fetchone()[0]

    assert identifiers == ["001", "02"]
    assert stored_body == body


def test_database_foreign_key_rejects_unknown_job_file(
    database_path: Path,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        with SQLiteConnectionFactory().connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO job_files (
                    job_pk,
                    file_role,
                    file_path,
                    exists_at_last_check,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    999_999,
                    "REPORT",
                    "D:/missing.xlsx",
                    0,
                    "2026-07-20T10:00:00",
                ),
            )
