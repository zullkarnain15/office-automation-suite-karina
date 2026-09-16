"""Legacy exporter compatibility tests using the existing DB2A readers."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory
from shared.config_manager import (
    AttendanceConfigurationReader,
    HRISConfigurationReader,
    OutlookRevisiConfigurationReader,
)
from shared.database.exporting import (
    export_attendance_legacy,
    export_hris_legacy,
    export_outlook_legacy,
)
from shared.database.importing.legacy import (
    map_attendance,
    map_hris,
    map_outlook,
)
from shared.database.importing.models import WorkbookIdentity
from shared.database.importing.workbook_detector import detect_workbook
from shared.database.importing.workbook_reader import read_workbook


@pytest.mark.parametrize(
    ("exporter", "identity", "mapper"),
    (
        (
            export_attendance_legacy,
            WorkbookIdentity.ATTENDANCE_LEGACY,
            map_attendance,
        ),
        (
            export_outlook_legacy,
            WorkbookIdentity.OUTLOOK_REVISI_LEGACY,
            map_outlook,
        ),
        (
            export_hris_legacy,
            WorkbookIdentity.HRIS_LEGACY,
            map_hris,
        ),
    ),
)
def test_legacy_export_is_detected_and_readable(
    configured_database: Path,
    tmp_path: Path,
    exporter: object,
    identity: WorkbookIdentity,
    mapper: object,
) -> None:
    output = tmp_path / f"{identity.value}.xlsx"
    result = exporter(configured_database, output)
    workbook, issues = read_workbook(output)
    mapped = mapper(workbook)

    assert result.workbook_identity is identity
    assert detect_workbook(output).identity is identity
    assert not issues
    assert mapped.tables


def test_hris_legacy_preserves_run_control_text(
    configured_database: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "hris.xlsx"
    export_hris_legacy(configured_database, output)
    workbook, _ = read_workbook(output)
    mapped = map_hris(workbook)

    assert {
        row["run_control_id"]
        for row in mapped.tables["hris_run_controls"]
    } == {"001", "02", "3"}


def test_attendance_legacy_is_readable_by_runtime_reader(
    configured_database: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "attendance.xlsx"
    export_attendance_legacy(configured_database, output)

    configuration = AttendanceConfigurationReader(output).read()
    assert configuration.general["Split_TXT_Rows"] == 10000
    assert configuration.output["Output_Root"] == r"C:\OAS-K\Output"
    assert [item.code for item in configuration.ho_mdb_list] == ["HO-01"]


def test_outlook_legacy_is_readable_by_runtime_reader(
    configured_database: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "outlook.xlsx"
    export_outlook_legacy(configured_database, output)

    configuration = OutlookRevisiConfigurationReader(output).read()
    assert configuration.general["Mailbox_SMTP"] == "oas-k@example.com"
    assert configuration.ho_senders[0].sender_email == "operator@example.com"
    assert configuration.reply_templates[0].body_template == (
        "Baris pertama\nBaris kedua {SENDER_NAME}"
    )


def test_hris_legacy_is_readable_by_runtime_reader(
    configured_database: Path,
    tmp_path: Path,
) -> None:
    output = tmp_path / "hris.xlsx"
    export_hris_legacy(configured_database, output)

    configuration = HRISConfigurationReader(output).read()
    assert configuration.general["HRIS_URL"] == "https://hris.example.com"
    assert [
        item.run_control_id for item in configuration.ho_run_controls
    ] == ["001", "02"]
    assert configuration.assisted_steps[0].step_name == "Isi Run Control"
    assert configuration.upload["Verification_Wait_Seconds"] == 2
    assert configuration.upload["Verification_Timeout_Seconds"] == 30
    assert (
        configuration.upload["Verification_Success_Texts"]
        == "Process Instance|Submitted|Queued"
    )
    assert (
        configuration.upload["Verification_Failure_Texts"]
        == "Error|Invalid|Failed"
    )


def test_outlook_legacy_uses_module_payroll_period_when_global_dates_cross_month(
    configured_database: Path,
    tmp_path: Path,
) -> None:
    with SQLiteConnectionFactory().connect(configured_database) as connection:
        connection.execute(
            "UPDATE global_settings SET period_end = '2026-07-15'"
        )

    output = tmp_path / "outlook.xlsx"
    export_outlook_legacy(configured_database, output)

    configuration = OutlookRevisiConfigurationReader(output).read()
    assert configuration.general["Payroll_Period"] == "07-2026"
