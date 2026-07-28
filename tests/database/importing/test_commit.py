"""Atomic import, confirmation, audit, and isolation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory
from shared.database.importing import (
    ChangeOperation,
    ConfigImportCommitRequest,
    ConfigImportService,
    ImportMode,
)
from shared.database.importing.exceptions import ConfigCommitError
from tests.database.importing.conftest import ATTENDANCE_WORKBOOK


def test_confirmation_required_preview_is_rejected_without_confirmation(
    db2_database: Path,
) -> None:
    service = ConfigImportService()
    preview = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    request = ConfigImportCommitRequest(
        preview=preview,
        modules=("ATTENDANCE",),
        mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
    )

    with pytest.raises(ConfigCommitError, match="confirmation"):
        service.commit(db2_database, request)


def test_attendance_commit_is_atomic_audited_and_module_isolated(
    db2_database: Path,
) -> None:
    service = ConfigImportService()
    preview = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    result = service.commit(
        db2_database,
        ConfigImportCommitRequest(
            preview=preview,
            modules=("ATTENDANCE",),
            mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
            confirmed=True,
            operator="tester",
        ),
    )

    with SQLiteConnectionFactory().connect(
        db2_database,
        read_only=True,
    ) as connection:
        attendance_count = connection.execute(
            "SELECT COUNT(*) FROM attendance_sources"
        ).fetchone()[0]
        hris_count = connection.execute(
            "SELECT COUNT(*) FROM hris_run_controls"
        ).fetchone()[0]
        outlook_count = connection.execute(
            "SELECT COUNT(*) FROM outlook_sender_master"
        ).fetchone()[0]
        batches = connection.execute(
            "SELECT COUNT(*) FROM config_import_batches"
        ).fetchone()[0]
        audits = connection.execute(
            """
            SELECT change_source, import_batch_id
            FROM configuration_audit
            """
        ).fetchall()

    assert result.committed is True
    assert attendance_count == 8
    assert hris_count == 0
    assert outlook_count == 0
    assert batches == 1
    assert audits
    assert all(row["change_source"] == "Excel Import" for row in audits)
    assert all(row["import_batch_id"] is not None for row in audits)


def test_global_settings_commit_is_a_separate_unit(
    db2_database: Path,
) -> None:
    service = ConfigImportService()
    preview = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    result = service.commit(
        db2_database,
        ConfigImportCommitRequest(
            preview=preview,
            modules=("GLOBAL",),
            mode=ImportMode.UPDATE_GLOBAL_SETTINGS,
            confirmed=True,
        ),
    )

    with SQLiteConnectionFactory().connect(
        db2_database,
        read_only=True,
    ) as connection:
        global_count = connection.execute(
            "SELECT COUNT(*) FROM global_settings"
        ).fetchone()[0]
        attendance_count = connection.execute(
            "SELECT COUNT(*) FROM attendance_settings"
        ).fetchone()[0]

    assert result.committed is True
    assert global_count == 1
    assert attendance_count == 0


def test_second_preview_is_unchanged_after_commit(
    db2_database: Path,
) -> None:
    service = ConfigImportService()
    first = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    service.commit(
        db2_database,
        ConfigImportCommitRequest(
            preview=first,
            modules=("ATTENDANCE",),
            mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
            confirmed=True,
        ),
    )

    second = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    operations = {
        change.operation
        for change in second.changes
        if change.module == "ATTENDANCE"
    }
    assert operations == {ChangeOperation.UNCHANGED}


def test_stale_preview_is_rejected(db2_database: Path) -> None:
    service = ConfigImportService()
    preview = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    with SQLiteConnectionFactory().connect(db2_database) as connection:
        connection.execute(
            """
            INSERT INTO attendance_settings (
                attendance_settings_id,
                use_global_output,
                use_global_period,
                split_txt_rows,
                generate_report_default,
                default_workflow,
                updated_at
            ) VALUES (1, 1, 1, 999, 1, 'HO', ?)
            """,
            ("2026-07-20T12:00:00",),
        )

    with pytest.raises(ConfigCommitError, match="stale"):
        service.commit(
            db2_database,
            ConfigImportCommitRequest(
                preview=preview,
                modules=("ATTENDANCE",),
                mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
                confirmed=True,
            ),
        )


def test_partial_write_rolls_back_and_records_failed_batch(
    db2_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ConfigImportService()
    first = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    service.commit(
        db2_database,
        ConfigImportCommitRequest(
            preview=first,
            modules=("ATTENDANCE",),
            mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
            confirmed=True,
        ),
    )
    second = service.preview(db2_database, [ATTENDANCE_WORKBOOK])

    original = service.transaction_service._insert_rows

    def fail_after_first_insert(connection, table, rows):
        original(connection, table, rows)
        raise RuntimeError("forced module failure")

    monkeypatch.setattr(
        service.transaction_service,
        "_insert_rows",
        fail_after_first_insert,
    )
    result = service.commit(
        db2_database,
        ConfigImportCommitRequest(
            preview=second,
            modules=("ATTENDANCE",),
            mode=ImportMode.REPLACE_MODULE_CONFIGURATION,
            confirmed=True,
        ),
    )

    with SQLiteConnectionFactory().connect(
        db2_database,
        read_only=True,
    ) as connection:
        sources = connection.execute(
            "SELECT COUNT(*) FROM attendance_sources"
        ).fetchone()[0]
        statuses = [
            row[0]
            for row in connection.execute(
                "SELECT status FROM config_import_batches ORDER BY import_batch_id"
            ).fetchall()
        ]

    assert result.committed is False
    assert sources == 8
    assert statuses == ["COMPLETED", "FAILED"]


def test_audit_secret_values_are_redacted() -> None:
    redact = ConfigImportService().transaction_service._redact

    assert redact("smtp_password", '"secret"') == "[REDACTED]"
    assert (
        redact(
            "settings",
            '{"token": "abc", "mailbox": "safe@example.com"}',
        )
        == '{"mailbox": "safe@example.com", "token": "[REDACTED]"}'
    )
