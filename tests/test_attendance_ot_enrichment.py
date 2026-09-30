"""Sprint 3 acceptance tests using representative, position-independent fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from shared.attendance_ot import (
    AttendanceOTAnalyticsQueryService,
    AttendanceOTEnrichmentService,
    AttendanceOTStorageService,
    ScheduleSubtype,
)
from shared.attendance_ot.models import SourceType
from shared.attendance_ot.readers import iter_source_rows
from shared.attendance_ot.schema import V1_TO_V2_STATEMENTS
from shared.database import SchemaManager


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


def _environment(tmp_path: Path):
    root = tmp_path / "Data"
    core = root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core, "test", create_parent=True)
    storage = AttendanceOTStorageService(_CoreStorage(root, core))
    status = storage.initialize()
    return storage, status.database_path


def _seed(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        now = "2026-09-01T00:00:00"
        for source_id, source_type in (
            (1, "ATTENDANCE_OT"),
            (2, "EMPLOYEE"),
            (3, "SCHEDULE"),
        ):
            connection.execute(
                """
                INSERT INTO source_registry (
                    source_id, source_type, source_path, filename, size_bytes,
                    modified_time_ns, row_count, status, imported_at, fingerprint,
                    error_detail, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 1, 0, 'NEW', ?, 'fixture', NULL, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    f"C:/fixture/{source_id}.xlsx",
                    f"{source_id}.xlsx",
                    now,
                    now,
                    now,
                    now,
                ),
            )
        employees = (
            ("E1", "Alice", "PG-HO", "HEAD OFFICE", "Finance", "Corporate", "Finance Analyst", "2026-01-01"),
            ("E1", "Alice", "PG-BR", "Branch Bandung", "Sales", "Retail", "Sales Officer", "2026-02-01"),
            ("E1", "Alice Future", "PG-FUT", "HEAD OFFICE", "Future", "Future Division", "Future Role", "2026-03-01"),
            ("E2", "Future Only", "PG-FUT", "HEAD OFFICE", "Future", "Future Division", "Future Role", "2026-03-01"),
            ("E3", "Branch User", "PG-BR", "Branch Surabaya", "Ops", "Operations", "Branch Staff", "2026-01-01"),
            ("E4", "HO User", "PG-HO", "  head   office ", "IT", "Technology", "Engineer", "2026-01-01"),
            ("E5", "Custom Rule", "PG-BR", "Branch Medan", "Ops", "Operations", "Branch Staff", "2026-01-01"),
        )
        for row_number, row in enumerate(employees, 2):
            (
                emplid,
                name,
                pay_group,
                location,
                department,
                division,
                job_title,
                snapshot,
            ) = row
            connection.execute(
                """
                INSERT INTO employee_records (
                    source_id, source_file, source_sheet, source_row, emplid,
                    name, pay_group, status, location_descr, regional, dept_desc,
                    organization_json, snapshot_date, division, job_title
                ) VALUES (2, 'employee.xlsx', 'Data', ?, ?, ?, ?, 'A', ?, 'WEST', ?, '{}', ?, ?, ?)
                """,
                (
                    row_number,
                    emplid,
                    name,
                    pay_group,
                    location,
                    department,
                    snapshot,
                    division,
                    job_title,
                ),
            )
        schedules = (
            ("E1", "WS_HO 3", "Explicit HO", "2026-01-01", "2026-01-31", "ignored"),
            ("E1", "WS_CCD", "Explicit CCD", "2026-02-01", None, "ignored"),
            ("E2", "WD", "Normal", "2026-01-01", None, None),
            ("E3", None, "Branch OTO", "2026-01-01", None, None),
            ("E4", "WD", "Normal", "2026-01-01", None, None),
            ("E5", "CUSTOM-1", "Custom branch", "2026-01-01", None, None),
        )
        for row_number, row in enumerate(schedules, 2):
            connection.execute(
                """
                INSERT INTO schedule_records (
                    source_id, source_file, source_sheet, source_row, emplid,
                    schedule_id, schedule_descr, effdt, end_effdt, rotation
                ) VALUES (3, 'schedule.xlsx', 'Assignment', ?, ?, ?, ?, ?, ?, ?)
                """,
                (row_number, *row),
            )
        connection.execute(
            """
            INSERT INTO schedule_rule_records (
                source_id, source_file, source_sheet, source_row, schedule_id,
                schedule_descr, rule_text, scheduled_in, scheduled_out, weekdays
            ) VALUES (3, 'schedule.xlsx', 'Rules', 2, 'CUSTOM-1',
                      'Custom branch', 'Jam kerja 07.45-16.15', NULL, NULL, 'WD,WE')
            """
        )
        attendance = (
            ("E1", "2026-01-02", "09:30", "23:59", 1, 30, 100, 20),
            ("E1", "2026-01-03", "09:45", "10:00", 0, 0, 0, 0),
            ("E1", "2026-01-04", "12:00", "13:00", 0, 0, 0, 0),
            ("E1", "2026-02-02", "08:31", "09:00", 2, 0, 200, 40),
            ("E2", "2026-02-02", "09:00", "17:00", 0, 0, 0, 0),
            ("E3", "2026-02-02", "08:31", "17:00", 0, 15, 10, 2),
            ("E4", "2026-02-02", "08:30", "17:30", 0, 0, 0, 0),
            ("E5", "2026-02-02", "07:50", "16:15", 0, 0, 0, 0),
        )
        for row_number, row in enumerate(attendance, 2):
            emplid, day, time_in, time_out, ot_hour, ot_minute, amount, meal = row
            connection.execute(
                """
                INSERT INTO attendance_records (
                    source_id, source_file, source_sheet, source_row, emplid,
                    date_in, time_in, date_out, time_out, overtime_hour,
                    overtime_minute, ot_amount, meal_ot_amount,
                    location_descr, name, paylink
                ) VALUES (1, 'attendance.xlsx', 'Data', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'source-location', 'source-name', 'source-paylink')
                """,
                (
                    row_number,
                    emplid,
                    day,
                    time_in,
                    day,
                    time_out,
                    ot_hour,
                    ot_minute,
                    amount,
                    meal,
                ),
            )


def test_enrichment_snapshot_schedule_late_overtime_and_aggregates(
    tmp_path: Path,
) -> None:
    storage, database = _environment(tmp_path)
    _seed(database)
    service = AttendanceOTEnrichmentService(batch_size=2)

    first = service.rebuild(database)
    second = service.rebuild(database)

    assert first.attendance_rows == second.attendance_rows == 8
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM enriched_attendance ORDER BY attendance_record_id"
        ).fetchall()
        assert rows[0]["employee_name"] == "Alice"
        assert rows[0]["pay_group"] == "PG-HO"
        assert rows[0]["division"] == "Corporate"
        assert rows[0]["job_title"] == "Finance Analyst"
        assert rows[0]["classification"] == "HO"
        assert rows[0]["scheduled_in"] == "09:30"
        assert rows[0]["late_status"] == "ON_TIME"
        assert rows[0]["total_ot_minutes"] == 90
        assert rows[0]["total_ot_hours"] == 1.5
        assert rows[0]["ot_amount"] == 100
        assert rows[0]["meal_ot_amount"] == 20
        assert rows[1]["workday_type"] == "WE"
        assert rows[1]["late_status"] == "LATE"
        assert rows[1]["late_minutes"] == 15
        assert rows[2]["workday_type"] == "OFF"
        assert rows[2]["late_status"] == "OFF_DAY"
        assert rows[3]["pay_group"] == "PG-BR"
        assert rows[3]["division"] == "Retail"
        assert rows[3]["job_title"] == "Sales Officer"
        assert rows[3]["resolved_schedule_id"] == "WS_CCD"
        assert rows[3]["scheduled_in"] == "08:30"
        assert rows[3]["late_minutes"] == 1
        assert rows[4]["employee_snapshot_id"] is None
        assert rows[4]["pay_group"] is None
        assert rows[5]["classification"] == "BRANCH"
        assert rows[5]["scheduled_in"] == "08:30"
        assert rows[5]["late_status"] == "LATE"
        assert rows[6]["classification"] == "HO"
        assert rows[6]["scheduled_in"] == "08:30"
        assert rows[6]["scheduled_out"] == "17:30"
        assert rows[7]["resolved_schedule_id"] == "CUSTOM-1"
        assert rows[7]["scheduled_in"] == "07:45"
        assert rows[7]["scheduled_out"] == "16:15"
        assert rows[7]["late_status"] == "LATE"
        assert rows[7]["late_minutes"] == 5
        assert (
            connection.execute("SELECT COUNT(*) FROM enriched_attendance").fetchone()[0]
            == 8
        )
        aggregate_count = connection.execute(
            "SELECT COUNT(*) FROM analytics_monthly_employee"
        ).fetchone()[0]
        assert aggregate_count == second.aggregate_rows

    query = AttendanceOTAnalyticsQueryService(storage)
    kpi = query.kpi_summary("2026-01-01", "2026-02-28")
    assert kpi.total_records == 8
    assert kpi.distinct_employees == 5
    assert kpi.late_records == 4
    assert kpi.total_ot_minutes == 225
    assert kpi.ot_amount == 310
    assert kpi.meal_ot_amount == 62
    assert query.top_late_employees("HO")[0]["emplid"] == "E1"
    assert query.top_late_branches()[0]["branch"] in {
        "Branch Bandung",
        "Branch Surabaya",
    }
    assert query.top_late_departments_ho()[0]["department"] == "Finance"
    assert query.top3_late_employee_ho()[0]["emplid"] == "E1"
    assert len(query.top3_late_employee_branch()) <= 3
    assert len(query.top3_late_branches()) <= 3
    assert len(query.top3_late_departments_ho()) <= 3
    assert query.monthly_late_matrix()


def test_employee_without_snapshot_date_is_timeless_fallback(
    tmp_path: Path,
) -> None:
    _storage, database = _environment(tmp_path)
    _seed(database)
    with sqlite3.connect(database) as connection:
        connection.executemany(
            """
            INSERT INTO employee_records (
                source_id, source_file, source_sheet, source_row, emplid,
                name, pay_group, status, location_descr, regional, dept_desc,
                organization_json, snapshot_date
            ) VALUES (2, 'employee.xlsx', 'Data', ?, 'E6', ?, ?, 'A', ?,
                      'WEST', ?, '{}', ?)
            """,
            (
                (100, "Timeless Employee", "PG-BASE", "Branch Base", "Base Dept", None),
                (101, "Dated Employee", "PG-DATED", "HEAD OFFICE", "Dated Dept", "2026-02-01"),
            ),
        )
        connection.executemany(
            """
            INSERT INTO attendance_records (
                source_id, source_file, source_sheet, source_row, emplid,
                date_in, time_in, date_out, time_out
            ) VALUES (1, 'attendance.xlsx', 'Data', ?, 'E6', ?, '08:30', ?, '17:30')
            """,
            (
                (100, "2026-01-15", "2026-01-15"),
                (101, "2026-03-15", "2026-03-15"),
            ),
        )

    AttendanceOTEnrichmentService(batch_size=2).rebuild(database)

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        snapshots = connection.execute(
            """
            SELECT snapshot_date, name FROM employee_snapshots
            WHERE emplid='E6' ORDER BY snapshot_date
            """
        ).fetchall()
        rows = connection.execute(
            """
            SELECT attendance_date, employee_name, branch, pay_group, department
            FROM enriched_attendance WHERE emplid='E6' ORDER BY attendance_date
            """
        ).fetchall()

    assert [(row["snapshot_date"], row["name"]) for row in snapshots] == [
        ("0001-01-01", "Timeless Employee"),
        ("2026-02-01", "Dated Employee"),
    ]
    assert tuple(rows[0]) == (
        "2026-01-15",
        "Timeless Employee",
        "Branch Base",
        "PG-BASE",
        "Base Dept",
    )
    assert tuple(rows[1]) == (
        "2026-03-15",
        "Dated Employee",
        "HEAD OFFICE",
        "PG-DATED",
        "Dated Dept",
    )


def test_missing_blank_na_and_unmapped_schedules_use_classification_defaults(
    tmp_path: Path,
) -> None:
    _storage, database = _environment(tmp_path)
    _seed(database)
    employees = (
        (200, "E6", "HO No Schedule", "HEAD OFFICE"),
        (201, "E7", "Branch NA", "Branch Bali"),
        (202, "E8", "HO Unknown", "HEAD OFFICE"),
        (203, "E9", "Branch Blank", "Branch Bogor"),
    )
    with sqlite3.connect(database) as connection:
        connection.executemany(
            """
            INSERT INTO employee_records (
                source_id, source_file, source_sheet, source_row, emplid,
                name, status, location_descr, dept_desc, snapshot_date
            ) VALUES (2, 'employee.xlsx', 'Data', ?, ?, ?, 'A', ?, 'Test',
                      '2026-01-01')
            """,
            employees,
        )
        connection.executemany(
            """
            INSERT INTO schedule_records (
                source_id, source_file, source_sheet, source_row, emplid,
                schedule_id, schedule_descr, effdt
            ) VALUES (3, 'schedule.xlsx', 'Assignment', ?, ?, ?, ?, '2026-01-01')
            """,
            (
                (201, "E7", "<N/A>", "<use default schedule>"),
                (202, "E8", "UNKNOWN-PROD", "Unmapped production code"),
                (203, "E9", None, None),
            ),
        )
        connection.executemany(
            """
            INSERT INTO attendance_records (
                source_id, source_file, source_sheet, source_row, emplid,
                date_in, time_in, date_out, time_out
            ) VALUES (1, 'attendance.xlsx', 'Data', ?, ?, '2026-02-02', ?,
                      '2026-02-02', '18:00')
            """,
            (
                (200, "E6", "08:45"),
                (201, "E7", "08:20"),
                (202, "E8", "08:31"),
                (203, "E9", "08:40"),
            ),
        )

    AttendanceOTEnrichmentService(batch_size=2).rebuild(database)

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT emplid, scheduled_in, scheduled_out, late_status, late_minutes
            FROM enriched_attendance WHERE emplid IN ('E6', 'E7', 'E8', 'E9')
            ORDER BY emplid
            """
        ).fetchall()
        defaults = connection.execute(
            """
            SELECT schedule_id, schedule_descr, rule_code, scheduled_in,
                   scheduled_out, is_builtin
            FROM schedule_rule_master
            WHERE schedule_id IN ('DEFAULT HO', 'DEFAULT BRANCH')
            ORDER BY schedule_id
            """
        ).fetchall()

    assert [tuple(row) for row in rows] == [
        ("E6", "08:30", "17:30", "LATE", 15),
        ("E7", "08:30", "16:30", "ON_TIME", 0),
        ("E8", "08:30", "17:30", "LATE", 1),
        ("E9", "08:30", "16:30", "LATE", 10),
    ]
    assert [tuple(row) for row in defaults] == [
        (
            "DEFAULT BRANCH",
            "Default Schedule Branch (fallback)",
            "DEFAULT_BRANCH",
            "08:30",
            "16:30",
            1,
        ),
        (
            "DEFAULT HO",
            "Default Schedule HO (fallback)",
            "DEFAULT_HO",
            "08:30",
            "17:30",
            1,
        ),
    ]


def test_schedule_rule_subtype_is_anchor_based_and_parses_dynamic_time(
    tmp_path: Path,
) -> None:
    source = tmp_path / "arbitrary-name.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rules"
    sheet.append(["Generated report"])
    sheet.append([None, "not the header"])
    sheet.append(["Keterangan", "Schedule Descr", "unused", "SCHEDULE ID"])
    sheet.append(["Jam kerja 07.45-16.15", "Custom branch", "x", "CUSTOM-1"])
    workbook.save(source)

    rows = list(iter_source_rows(source, SourceType.SCHEDULE))

    assert len(rows) == 1
    assert rows[0].source_row == 4
    assert rows[0].schedule_subtype is ScheduleSubtype.RULE
    assert rows[0].headers["schedule id"] == 3


def test_v3_indexes_support_high_volume_lookup_shapes(tmp_path: Path) -> None:
    _storage, database = _environment(tmp_path)
    with sqlite3.connect(database) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
    assert {
        "idx_employee_snapshots_lookup",
        "idx_schedule_records_emplid_effdt",
        "idx_enriched_attendance_employee_date",
        "idx_enriched_attendance_late_date",
        "idx_monthly_employee_class_late",
        "idx_monthly_employee_branch_late",
        "idx_monthly_employee_department_late",
        "idx_monthly_employee_division_late",
        "idx_monthly_employee_pay_group_late",
        "idx_enriched_attendance_division_date",
    } <= indexes


def test_v2_to_v3_migration_is_idempotent_and_preserves_raw_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Data"
    core = root / "database" / "OAS-K.db"
    SchemaManager().initialize_database(core, "test", create_parent=True)
    storage = AttendanceOTStorageService(_CoreStorage(root, core))
    database = storage.database_path(root)
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE analytics_metadata (
                metadata_id INTEGER PRIMARY KEY CHECK (metadata_id=1),
                database_uuid TEXT NOT NULL UNIQUE,
                schema_version INTEGER NOT NULL,
                initialized_at TEXT NOT NULL,
                last_migrated_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO analytics_metadata VALUES (1, 'v2-fixture', 2, '2026-01-01', NULL)"
        )
        for statement in V1_TO_V2_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO source_registry (
                source_id, source_type, source_path, filename, size_bytes,
                modified_time_ns, row_count, status, imported_at, fingerprint,
                error_detail, last_seen_at, created_at, updated_at
            ) VALUES (1, 'ATTENDANCE_OT', 'C:/old.xlsx', 'old.xlsx', 1, 1,
                      1, 'NEW', '2026-01-01', 'old', NULL,
                      '2026-01-01', '2026-01-01', '2026-01-01')
            """
        )
        connection.execute(
            """
            INSERT INTO source_registry (
                source_id, source_type, source_path, filename, size_bytes,
                modified_time_ns, row_count, status, imported_at, fingerprint,
                error_detail, last_seen_at, created_at, updated_at
            ) VALUES (2, 'EMPLOYEE', 'C:/employee.xlsx', 'employee.xlsx', 1, 1,
                      1, 'NEW', '2026-01-01', 'employee', NULL,
                      '2026-01-01', '2026-01-01', '2026-01-01')
            """
        )
        connection.execute(
            """
            INSERT INTO attendance_records (
                source_id, source_file, source_sheet, source_row, emplid,
                date_in, time_in
            ) VALUES (1, 'old.xlsx', 'Sheet1', 2, '00001', '2026-01-01', '08:30')
            """
        )
        connection.execute(
            """
            INSERT INTO employee_records (
                source_id, source_file, source_sheet, source_row, emplid,
                name, organization_json
            ) VALUES (
                2, 'employee.xlsx', 'Sheet1', 2, '00001', 'Legacy Employee',
                '{"bus. desc.":"Legacy Division","jobcd desc":"Legacy Job"}'
            )
            """
        )
        connection.execute("PRAGMA user_version=2")

    first = storage.initialize()
    second = storage.initialize()

    assert first.schema_version == second.schema_version == 5
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT emplid FROM attendance_records").fetchone()[0]
            == "00001"
        )
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        assert connection.execute(
            "SELECT division, job_title FROM employee_records WHERE emplid='00001'"
        ).fetchone() == ("Legacy Division", "Legacy Job")
