"""Sprint 2 acceptance tests for scanner, readers, migration, and import."""

from __future__ import annotations

import sqlite3
import tracemalloc
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from shared.attendance_ot import (
    ANALYTICS_SCHEMA_VERSION,
    AttendanceOTImportService,
    AttendanceOTStorageService,
)
from shared.attendance_ot.models import SourceType
from shared.attendance_ot.readers import date_text, period_date_text, time_text
from shared.attendance_ot.scanner import scan_source_folder
from shared.database import SchemaManager
from ui.services.database_settings_service import DatabaseSettingsService
from ui.services.protocols import AttendanceOTSourceDraft


class _CoreStorage:
    def __init__(self, root: Path, database: Path) -> None:
        self.root = root
        self.database = database

    def resolve_status(self):
        return SimpleNamespace(
            data_root=self.root,
            database_path=self.database,
            database_valid=True,
        )


@pytest.mark.parametrize(
    "value,expected",
    [
        (date(2026, 9, 30), "2026-09-30"),
        (datetime(2026, 9, 30, 8, 20), "2026-09-30"),
        ("2026-09-30", "2026-09-30"),
        ("2026/9/30 00:00:00", "2026-09-30"),
        ("09/30/2026", "2026-09-30"),
        ("9/1/2026 12:00:00 AM", "2026-09-01"),
        (20260930, "2026-09-30"),
    ],
)
def test_date_text_normalizes_excel_iso_and_production_mdy(value, expected):
    assert date_text(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (time(8, 20), "08:20:00"),
        (datetime(2026, 9, 1, 8, 20), "08:20:00"),
        ("08:20:00", "08:20:00"),
        ("8:20:00 AM", "08:20:00"),
        ("6:30 PM", "18:30:00"),
        ("08.20.00", "08:20:00"),
        ("12:00 AM", "00:00:00"),
        ("12:00 PM", "12:00:00"),
        (0.5, "12:00:00"),
    ],
)
def test_time_text_normalizes_excel_24_hour_and_ampm(value, expected):
    assert time_text(value) == expected


def test_invalid_or_ambiguous_date_and_time_are_rejected():
    with pytest.raises(ValueError, match="Tanggal tidak valid"):
        date_text("02/30/2026")
    with pytest.raises(ValueError, match="Tanggal"):
        date_text("30/09/2026")
    with pytest.raises(ValueError, match="Format waktu tidak didukung"):
        time_text("25:00 PM")
    assert period_date_text("09/2026") == "2026-09-01"
    with pytest.raises(ValueError, match="Periode tidak valid"):
        period_date_text("13/2026")


def _xlsx(path: Path, preamble: int, headers: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Imported Data")
    for index in range(preamble):
        sheet.append([f"Report preamble {index + 1}"])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def _xls(path: Path, preamble: int, headers: list[str], rows: list[list]) -> None:
    xlwt = pytest.importorskip("xlwt")
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Employee Master")
    for index in range(preamble):
        sheet.write(index, 0, f"Employee report {index + 1}")
    header_row = preamble
    for column, value in enumerate(headers):
        sheet.write(header_row, column, value)
    for row_offset, row in enumerate(rows, start=header_row + 1):
        for column, value in enumerate(row):
            sheet.write(row_offset, column, value)
    workbook.save(str(path))


@pytest.fixture
def import_environment(tmp_path: Path):
    data_root = tmp_path / "Data"
    core_database = data_root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core_database, "test", create_parent=True)
    folders = {
        "attendance": tmp_path / "sources" / "attendance",
        "employee": tmp_path / "sources" / "employee",
        "schedule": tmp_path / "sources" / "schedule",
    }
    for folder in folders.values():
        folder.mkdir(parents=True)
    settings = DatabaseSettingsService()
    settings.save_attendance_ot_source_preferences(
        core_database,
        AttendanceOTSourceDraft(
            str(folders["attendance"]),
            str(folders["employee"]),
            str(folders["schedule"]),
        ),
    )
    storage = AttendanceOTStorageService(_CoreStorage(data_root, core_database))
    service = AttendanceOTImportService(storage, settings, batch_size=2)
    return data_root, core_database, folders, storage, service


def _create_three_sources(folders: dict[str, Path]) -> tuple[Path, Path, Path]:
    attendance = folders["attendance"] / "nested" / "random_name.xlsx"
    attendance_headers = [
        " Name ",
        "TIME   IN",
        " emplid ",
        "Date In",
        "Date Out",
        "Time Out",
        "Overtime Hour",
        "Overtime Minute",
        "OT Amount",
        "Meal OT Amount",
        "Location Descr",
        "Paylink",
    ]
    _xlsx(
        attendance,
        4,
        attendance_headers,
        [
            [
                "Alice",
                "08:00",
                "000123",
                "2026-09-01",
                "2026-09-01",
                "17:00",
                1,
                30,
                100,
                20,
                "HQ",
                "PG1",
            ],
            [
                "Bob",
                "08:15",
                "000124",
                "2026-09-01",
                "2026-09-01",
                "18:00",
                2,
                0,
                200,
                20,
                "HQ",
                "PG1",
            ],
        ],
    )
    employee = folders["employee"] / "employee_data.xls"
    _xls(
        employee,
        2,
        [
            "REGIONAL",
            " emplid",
            "Dept   Desc",
            "NAME",
            "STATUS",
            "Pay Group",
            "Location Descr",
            "Bus.   Desc.",
            "JobCd   Desc",
            "Business Unit",
        ],
        [
            [
                "WEST",
                "000456",
                "People",
                "Carol",
                "A",
                "MTH",
                "Branch",
                "Retail Banking",
                "Service Officer",
                "BU01",
            ]
        ],
    )
    schedule = folders["schedule"] / "deep" / "schedule_book.xlsx"
    _xlsx(
        schedule,
        7,
        ["ROTATION", "Schedule Descr", "EMPLID", "END EFFDT", "EFFDT", "Schedule ID"],
        [["R1", "Normal", "000789", "2026-12-31", "2026-01-01", "SCH01"]],
    )
    return attendance, employee, schedule


def test_refresh_canonicalizes_production_mdy_and_ampm(
    import_environment,
) -> None:
    data_root, _core, folders, storage, service = import_environment
    source = folders["attendance"] / "production-format.xlsx"
    _xlsx(
        source,
        1,
        [
            "EMPLID",
            "Date In",
            "Time In",
            "Date Out",
            "Time Out",
            "Overtime Hour",
            "Overtime Minute",
            "OT Amount",
            "Meal OT Amount",
            "Location Descr",
            "Name",
            "Paylink",
        ],
        [
            [
                "000123",
                "09/30/2026",
                "8:20:00 AM",
                "09/30/2026",
                "6:30 PM",
                1,
                0,
                100,
                20,
                "HEAD OFFICE",
                "Alice",
                "PG1",
            ]
        ],
    )

    result = service.refresh()

    assert result.files_error == 0
    database = storage.database_path(data_root)
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT date_in,time_in,date_out,time_out FROM attendance_records"
        ).fetchone()
    assert row == ("2026-09-30", "08:20:00", "2026-09-30", "18:30:00")


def test_new_import_is_recursive_dynamic_batched_and_supports_xls_xlsx(
    import_environment,
) -> None:
    data_root, _core, folders, storage, service = import_environment
    attendance, employee, schedule = _create_three_sources(folders)
    invalid = folders["attendance"] / "broken.xlsx"
    invalid.write_bytes(b"not an excel workbook")

    progress = []
    result = service.refresh(progress.append)

    assert attendance.is_file() and employee.is_file() and schedule.is_file()
    assert result.files_discovered == 4
    assert result.files_processed == 3
    assert result.files_error == 1
    assert result.rows_imported == 4
    assert [event.phase for event in progress][0] == "SCANNING"
    assert [event.phase for event in progress][-1] == "COMPLETED"
    database = storage.database_path(data_root)
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0]
            == 2
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM employee_records").fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM schedule_records").fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT emplid FROM attendance_records ORDER BY source_row LIMIT 1"
            ).fetchone()[0]
            == "000123"
        )
        employee_row = connection.execute(
            "SELECT emplid, division, job_title, organization_json "
            "FROM employee_records"
        ).fetchone()
        assert employee_row[0] == "000456"
        assert employee_row[1:3] == ("Retail Banking", "Service Officer")
        assert '"business unit":"BU01"' in employee_row[3]
        provenance = connection.execute(
            "SELECT source_file, source_sheet, source_row FROM schedule_records"
        ).fetchone()
        assert Path(provenance[0]).name == "schedule_book.xlsx"
        assert provenance[1] == "Imported Data"
        assert provenance[2] == 9
    broken = next(item for item in result.sources if item.filename == "broken.xlsx")
    assert broken.status == "ERROR"
    assert broken.error_detail


def test_unchanged_is_skipped_and_changed_replaces_without_duplicates(
    import_environment,
) -> None:
    data_root, _core, folders, storage, service = import_environment
    attendance, _employee, _schedule = _create_three_sources(folders)
    initial_plan = service.prepare_refresh()
    assert initial_plan.count("NEW") == 3
    first = service.refresh(plan=initial_plan)
    assert first.files_processed == 3

    unchanged_plan = service.prepare_refresh()
    assert unchanged_plan.count("UNCHANGED") == 3
    second = service.refresh(plan=unchanged_plan)
    assert second.files_processed == 0
    assert second.files_skipped == 3
    assert second.rows_imported == 0

    _xlsx(
        attendance,
        1,
        [
            "EMPLID",
            "Date In",
            "Time In",
            "Date Out",
            "Time Out",
            "Overtime Hour",
            "Overtime Minute",
            "OT Amount",
            "Meal OT Amount",
            "Location Descr",
            "Name",
            "Paylink",
        ],
        [
            [
                "000123",
                "2026-09-01",
                "08:00",
                "2026-09-01",
                "17:00",
                1,
                0,
                100,
                20,
                "HQ",
                "Alice",
                "PG1",
            ],
            [
                "000125",
                "2026-09-02",
                "08:00",
                "2026-09-02",
                "17:00",
                1,
                0,
                100,
                20,
                "HQ",
                "Dina",
                "PG1",
            ],
            [
                "000126",
                "2026-09-03",
                "08:00",
                "2026-09-03",
                "17:00",
                1,
                0,
                100,
                20,
                "HQ",
                "Evan",
                "PG1",
            ],
        ],
    )
    changed = service.refresh()
    source = next(item for item in changed.sources if item.filename == attendance.name)
    assert source.status == "CHANGED"
    assert source.row_count == 3
    database = storage.database_path(data_root)
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0]
            == 3
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE emplid='000123'"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM enriched_attendance").fetchone()[0]
            == 3
        )
        assert (
            connection.execute(
                "SELECT COUNT(DISTINCT attendance_record_id) FROM enriched_attendance"
            ).fetchone()[0]
            == 3
        )


def test_corrupt_changed_file_preserves_previous_rows_and_isolates_error(
    import_environment,
) -> None:
    data_root, _core, folders, storage, service = import_environment
    attendance, _employee, _schedule = _create_three_sources(folders)
    service.refresh()
    attendance.write_bytes(b"corrupt replacement")

    result = service.refresh()

    assert result.files_error == 1
    source = next(item for item in result.sources if item.filename == attendance.name)
    assert source.status == "ERROR"
    database = storage.database_path(data_root)
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0]
            == 2
        )


def test_missing_marks_registry_without_deleting_historical_rows(
    import_environment,
) -> None:
    data_root, _core, folders, storage, service = import_environment
    _attendance, _employee, schedule = _create_three_sources(folders)
    service.refresh()
    schedule.unlink()

    result = service.refresh()

    source = next(item for item in result.sources if item.filename == schedule.name)
    assert source.status == "MISSING"
    assert result.files_missing == 1
    with sqlite3.connect(storage.database_path(data_root)) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM schedule_records").fetchone()[0]
            == 1
        )


def test_v1_database_migrates_sequentially_to_v3_idempotently(tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    core_database = data_root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core_database, "test", create_parent=True)
    storage = AttendanceOTStorageService(_CoreStorage(data_root, core_database))
    database = storage.database_path(data_root)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE analytics_metadata (
                metadata_id INTEGER PRIMARY KEY,
                database_uuid TEXT NOT NULL UNIQUE,
                schema_version INTEGER NOT NULL,
                initialized_at TEXT NOT NULL,
                last_migrated_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO analytics_metadata VALUES (1, 'v1-test', 1, '2026-01-01T00:00:00', NULL)"
        )
        connection.execute("PRAGMA user_version = 1")

    first = storage.initialize()
    second = storage.initialize()

    assert first.schema_version == ANALYTICS_SCHEMA_VERSION == 5
    assert second.schema_version == 5
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {
        "source_registry",
        "attendance_records",
        "employee_records",
        "schedule_records",
        "schedule_rule_records",
        "employee_snapshots",
        "schedule_rule_master",
        "enriched_attendance",
        "analytics_monthly_employee",
    } <= tables


def test_large_xlsx_import_keeps_peak_memory_bounded(tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    core_database = data_root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core_database, "test", create_parent=True)
    source_root = tmp_path / "large-source"
    source_root.mkdir()
    source = source_root / "large.xlsx"
    headers = [
        "EMPLID",
        "Date In",
        "Time In",
        "Date Out",
        "Time Out",
        "Overtime Hour",
        "Overtime Minute",
        "OT Amount",
        "Meal OT Amount",
        "Location Descr",
        "Name",
        "Paylink",
    ]
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Rows")
    sheet.append(["Large import fixture"])
    sheet.append(headers)
    for index in range(20_000):
        sheet.append(
            [
                f"{index:08d}",
                "2026-09-01",
                "08:00",
                "2026-09-01",
                "17:00",
                1,
                0,
                100,
                20,
                "HQ",
                f"Employee {index}",
                "PG1",
            ]
        )
    workbook.save(source)
    settings = DatabaseSettingsService()
    settings.save_attendance_ot_source_preferences(
        core_database,
        AttendanceOTSourceDraft(attendance_ot_folder=str(source_root)),
    )
    storage = AttendanceOTStorageService(_CoreStorage(data_root, core_database))
    service = AttendanceOTImportService(storage, settings, batch_size=500)

    tracemalloc.start()
    result = service.refresh()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert result.rows_imported == 20_000
    assert peak < 64 * 1024 * 1024


def test_scanner_handles_more_than_fifty_files_recursively(tmp_path: Path) -> None:
    root = tmp_path / "sources"
    for index in range(55):
        folder = root / f"group-{index % 5}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"source-{index}.xlsx").write_bytes(f"fixture-{index}".encode())

    candidates, issues = scan_source_folder(root, SourceType.ATTENDANCE_OT)

    assert len(candidates) == 55
    assert not issues
