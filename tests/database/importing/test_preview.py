"""Read-only preview, issue, and conflict tests."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from shared.database import SQLiteConnectionFactory
from shared.database.importing import ChangeOperation, ConfigImportService
from tests.database.importing.conftest import (
    ATTENDANCE_WORKBOOK,
    HRIS_WORKBOOK,
    OUTLOOK_DUPLICATE,
    OUTLOOK_WORKBOOK,
)


def test_attendance_preview_detects_duplicate_period_and_development_data(
    db2_database: Path,
) -> None:
    preview = ConfigImportService().preview(
        db2_database,
        [ATTENDANCE_WORKBOOK],
    )
    codes = {issue.code for issue in preview.issues}

    assert preview.can_commit is True
    assert preview.confirmation_required is True
    assert "ATTENDANCE_DUPLICATE_PERIOD_KEY" in codes
    assert "DEVELOPMENT_PATH_DETECTED" in codes
    assert "SAMPLE_MDB_DETECTED" in codes


def test_outlook_duplicate_and_high_risk_settings_are_detected(
    db2_database: Path,
) -> None:
    preview = ConfigImportService().preview(
        db2_database,
        [OUTLOOK_WORKBOOK, OUTLOOK_DUPLICATE],
    )
    codes = {issue.code for issue in preview.issues}

    assert "DUPLICATE_WORKBOOK_DETECTED" in codes
    assert "OUTLOOK_AUTOMATIC_SEND_ENABLED" in codes
    assert "TEST_SENDER_DETECTED" in codes


def test_hris_mock_url_warning_is_critical(
    db2_database: Path,
    tmp_path: Path,
) -> None:
    mock_workbook = tmp_path / "hris-mock-url.xlsx"
    workbook = load_workbook(HRIS_WORKBOOK)
    general = workbook["General"]
    hris_url_row = next(
        row
        for row in range(1, general.max_row + 1)
        if general.cell(row, 1).value == "HRIS_URL"
    )
    general.cell(hris_url_row, 2, "http://mock.hris.local")
    workbook.save(mock_workbook)
    workbook.close()

    preview = ConfigImportService().preview(
        db2_database,
        [mock_workbook],
    )
    issue = next(
        item
        for item in preview.issues
        if item.code == "HRIS_MOCK_URL_DETECTED"
    )

    assert issue.confirmation_required is True
    assert issue.severity.value == "CRITICAL"


def test_global_output_and_period_conflicts_are_not_silently_resolved(
    db2_database: Path,
) -> None:
    preview = ConfigImportService().preview(
        db2_database,
        [ATTENDANCE_WORKBOOK, HRIS_WORKBOOK, OUTLOOK_WORKBOOK],
    )
    codes = {issue.code for issue in preview.issues}

    assert "GLOBAL_OUTPUT_CONFLICT" in codes
    assert "GLOBAL_PERIOD_CONFLICT" in codes
    assert preview.can_commit is False
    assert "GLOBAL" not in preview.modules


def test_explicit_global_resolution_makes_conflict_committable(
    db2_database: Path,
) -> None:
    preview = ConfigImportService().preview(
        db2_database,
        [ATTENDANCE_WORKBOOK, HRIS_WORKBOOK],
        global_resolution={
            "output_root": "D:/Chosen/Output",
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
        },
    )
    codes = {issue.code for issue in preview.issues}

    assert "GLOBAL_OUTPUT_CONFLICT" not in codes
    assert "GLOBAL_PERIOD_CONFLICT" not in codes
    assert "GLOBAL_CONFLICT_RESOLVED" in codes
    assert "GLOBAL" in preview.modules
    assert preview.can_commit is True
    assert preview.confirmation_required is True


def test_preview_does_not_write_database(db2_database: Path) -> None:
    factory = SQLiteConnectionFactory()
    with factory.connect(db2_database, read_only=True) as connection:
        before = _counts(connection)

    ConfigImportService().preview(db2_database, [ATTENDANCE_WORKBOOK])

    with factory.connect(db2_database, read_only=True) as connection:
        after = _counts(connection)
    assert before == after


def test_preview_shows_insert_and_then_unchanged(
    db2_database: Path,
) -> None:
    service = ConfigImportService()
    first = service.preview(db2_database, [ATTENDANCE_WORKBOOK])
    operations = {
        change.operation
        for change in first.changes
        if change.module == "ATTENDANCE"
    }

    assert operations == {ChangeOperation.INSERT}


def test_unknown_workbook_preview_cannot_commit(
    db2_database: Path,
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.xlsx"
    workbook = Workbook()
    workbook.active.title = "Unknown"
    workbook.save(path)
    workbook.close()

    preview = ConfigImportService().preview(db2_database, [path])

    assert preview.can_commit is False
    assert any(issue.code == "WORKBOOK_UNKNOWN" for issue in preview.issues)


def _counts(connection) -> tuple[int, int, int, int]:
    return tuple(
        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "attendance_settings",
            "attendance_sources",
            "config_import_batches",
            "configuration_audit",
        )
    )
