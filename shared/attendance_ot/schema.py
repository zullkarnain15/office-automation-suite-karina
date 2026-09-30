"""Versioned schema migrations for the isolated analytics database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp

ANALYTICS_SCHEMA_VERSION = 5

V1_TO_V2_STATEMENTS = (
    """
    CREATE TABLE source_registry (
        source_id INTEGER PRIMARY KEY,
        source_type TEXT NOT NULL CHECK (
            source_type IN ('ATTENDANCE_OT', 'EMPLOYEE', 'SCHEDULE')
        ),
        source_path TEXT NOT NULL COLLATE NOCASE UNIQUE,
        filename TEXT NOT NULL,
        size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
        modified_time_ns INTEGER NOT NULL CHECK (modified_time_ns >= 0),
        row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
        status TEXT NOT NULL CHECK (
            status IN ('NEW', 'CHANGED', 'UNCHANGED', 'ERROR', 'MISSING')
        ),
        imported_at TEXT,
        fingerprint TEXT,
        error_detail TEXT,
        last_seen_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_source_registry_type_status "
    "ON source_registry (source_type, status)",
    "CREATE INDEX idx_source_registry_imported_at "
    "ON source_registry (imported_at DESC)",
    """
    CREATE TABLE attendance_records (
        attendance_record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        source_file TEXT NOT NULL,
        source_sheet TEXT NOT NULL,
        source_row INTEGER NOT NULL CHECK (source_row > 0),
        emplid TEXT NOT NULL,
        date_in TEXT,
        time_in TEXT,
        date_out TEXT,
        time_out TEXT,
        overtime_hour REAL,
        overtime_minute REAL,
        ot_amount REAL,
        meal_ot_amount REAL,
        location_descr TEXT,
        name TEXT,
        paylink TEXT,
        FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (source_id, source_sheet, source_row)
    )
    """,
    "CREATE INDEX idx_attendance_records_source ON attendance_records (source_id)",
    "CREATE INDEX idx_attendance_records_emplid_date "
    "ON attendance_records (emplid, date_in)",
    """
    CREATE TABLE employee_records (
        employee_record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        source_file TEXT NOT NULL,
        source_sheet TEXT NOT NULL,
        source_row INTEGER NOT NULL CHECK (source_row > 0),
        emplid TEXT NOT NULL,
        name TEXT,
        pay_group TEXT,
        status TEXT,
        location_descr TEXT,
        regional TEXT,
        dept_desc TEXT,
        organization_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (source_id, source_sheet, source_row)
    )
    """,
    "CREATE INDEX idx_employee_records_source ON employee_records (source_id)",
    "CREATE INDEX idx_employee_records_emplid ON employee_records (emplid)",
    """
    CREATE TABLE schedule_records (
        schedule_record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        source_file TEXT NOT NULL,
        source_sheet TEXT NOT NULL,
        source_row INTEGER NOT NULL CHECK (source_row > 0),
        emplid TEXT NOT NULL,
        schedule_id TEXT,
        schedule_descr TEXT,
        effdt TEXT,
        end_effdt TEXT,
        rotation TEXT,
        FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (source_id, source_sheet, source_row)
    )
    """,
    "CREATE INDEX idx_schedule_records_source ON schedule_records (source_id)",
    "CREATE INDEX idx_schedule_records_emplid_effdt "
    "ON schedule_records (emplid, effdt)",
)

V2_TO_V3_STATEMENTS = (
    "ALTER TABLE employee_records ADD COLUMN snapshot_date TEXT",
    "ALTER TABLE analytics_metadata ADD COLUMN derived_dirty INTEGER NOT NULL DEFAULT 1 CHECK (derived_dirty IN (0, 1))",
    "ALTER TABLE analytics_metadata ADD COLUMN derived_refreshed_at TEXT",
    "ALTER TABLE analytics_metadata ADD COLUMN derived_error TEXT",
    "CREATE INDEX idx_employee_records_emplid_snapshot ON employee_records (emplid, snapshot_date DESC)",
    """
    CREATE TABLE schedule_rule_records (
        schedule_rule_record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        source_file TEXT NOT NULL,
        source_sheet TEXT NOT NULL,
        source_row INTEGER NOT NULL CHECK (source_row > 0),
        schedule_id TEXT,
        schedule_descr TEXT,
        rule_text TEXT,
        scheduled_in TEXT,
        scheduled_out TEXT,
        weekdays TEXT,
        FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (source_id, source_sheet, source_row)
    )
    """,
    "CREATE INDEX idx_schedule_rule_records_source ON schedule_rule_records (source_id)",
    "CREATE INDEX idx_schedule_rule_records_key ON schedule_rule_records (schedule_id COLLATE NOCASE, schedule_descr COLLATE NOCASE)",
    """
    CREATE TABLE employee_snapshots (
        employee_snapshot_id INTEGER PRIMARY KEY,
        source_employee_record_id INTEGER NOT NULL UNIQUE,
        emplid TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        snapshot_period TEXT NOT NULL,
        name TEXT,
        pay_group TEXT,
        status TEXT,
        location_descr TEXT,
        regional TEXT,
        dept_desc TEXT,
        classification TEXT NOT NULL CHECK (classification IN ('HO', 'BRANCH')),
        FOREIGN KEY (source_employee_record_id)
            REFERENCES employee_records(employee_record_id) ON DELETE RESTRICT
    )
    """,
    "CREATE INDEX idx_employee_snapshots_lookup ON employee_snapshots (emplid, snapshot_date DESC, employee_snapshot_id DESC)",
    "CREATE INDEX idx_employee_snapshots_period ON employee_snapshots (snapshot_period, emplid)",
    """
    CREATE TABLE schedule_rule_master (
        schedule_rule_id INTEGER PRIMARY KEY,
        source_schedule_rule_record_id INTEGER UNIQUE,
        schedule_key TEXT NOT NULL COLLATE NOCASE,
        schedule_id TEXT,
        schedule_descr TEXT,
        rule_code TEXT NOT NULL,
        scheduled_in TEXT,
        scheduled_out TEXT,
        weekdays TEXT NOT NULL DEFAULT 'WD,WE',
        priority INTEGER NOT NULL DEFAULT 0,
        is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
        FOREIGN KEY (source_schedule_rule_record_id)
            REFERENCES schedule_rule_records(schedule_rule_record_id) ON DELETE RESTRICT
    )
    """,
    "CREATE INDEX idx_schedule_rule_master_lookup ON schedule_rule_master (schedule_key, priority DESC)",
    """
    CREATE TABLE enriched_attendance (
        attendance_record_id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        emplid TEXT NOT NULL,
        attendance_date TEXT NOT NULL,
        actual_time_in TEXT,
        actual_time_out TEXT,
        employee_snapshot_id INTEGER,
        employee_name TEXT,
        pay_group TEXT,
        branch TEXT,
        classification TEXT,
        department TEXT,
        schedule_record_id INTEGER,
        resolved_schedule_id TEXT,
        resolved_schedule_descr TEXT,
        resolved_schedule_effdt TEXT,
        scheduled_in TEXT,
        scheduled_out TEXT,
        workday_type TEXT,
        late_status TEXT NOT NULL CHECK (
            late_status IN ('ON_TIME', 'LATE', 'OFF_DAY', 'NO_SCHEDULE', 'UNMAPPED_SCHEDULE')
        ),
        late_minutes INTEGER NOT NULL DEFAULT 0 CHECK (late_minutes >= 0),
        overtime_hour REAL NOT NULL DEFAULT 0,
        overtime_minute REAL NOT NULL DEFAULT 0,
        total_ot_minutes REAL NOT NULL DEFAULT 0,
        total_ot_hours REAL NOT NULL DEFAULT 0,
        ot_amount REAL NOT NULL DEFAULT 0,
        meal_ot_amount REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (attendance_record_id) REFERENCES attendance_records(attendance_record_id) ON DELETE RESTRICT,
        FOREIGN KEY (employee_snapshot_id) REFERENCES employee_snapshots(employee_snapshot_id) ON DELETE RESTRICT,
        FOREIGN KEY (schedule_record_id) REFERENCES schedule_records(schedule_record_id) ON DELETE RESTRICT
    )
    """,
    "CREATE INDEX idx_enriched_attendance_date ON enriched_attendance (attendance_date)",
    "CREATE INDEX idx_enriched_attendance_employee_date ON enriched_attendance (emplid, attendance_date)",
    "CREATE INDEX idx_enriched_attendance_late_date ON enriched_attendance (late_status, attendance_date)",
    "CREATE INDEX idx_enriched_attendance_class_date ON enriched_attendance (classification, attendance_date)",
    "CREATE INDEX idx_enriched_attendance_branch_date ON enriched_attendance (branch, attendance_date)",
    "CREATE INDEX idx_enriched_attendance_department_date ON enriched_attendance (department, attendance_date)",
    "CREATE INDEX idx_enriched_attendance_pay_group_date ON enriched_attendance (pay_group, attendance_date)",
    """
    CREATE TABLE analytics_monthly_employee (
        year_month TEXT NOT NULL,
        emplid TEXT NOT NULL,
        employee_name TEXT NOT NULL DEFAULT '',
        classification TEXT NOT NULL DEFAULT '',
        branch TEXT NOT NULL DEFAULT '',
        department TEXT NOT NULL DEFAULT '',
        pay_group TEXT NOT NULL DEFAULT '',
        total_records INTEGER NOT NULL,
        late_count INTEGER NOT NULL,
        total_ot_minutes REAL NOT NULL,
        ot_amount REAL NOT NULL,
        meal_ot_amount REAL NOT NULL,
        PRIMARY KEY (year_month, emplid, employee_name, classification, branch, department, pay_group)
    ) WITHOUT ROWID
    """,
    "CREATE INDEX idx_monthly_employee_class_late ON analytics_monthly_employee (year_month, classification, late_count DESC)",
    "CREATE INDEX idx_monthly_employee_branch_late ON analytics_monthly_employee (year_month, branch, late_count DESC)",
    "CREATE INDEX idx_monthly_employee_department_late ON analytics_monthly_employee (year_month, department, late_count DESC)",
    "CREATE INDEX idx_monthly_employee_pay_group_late ON analytics_monthly_employee (year_month, pay_group, late_count DESC)",
)


class AnalyticsSchemaManager:
    def __init__(self, factory: SQLiteConnectionFactory | None = None) -> None:
        self.factory = factory or SQLiteConnectionFactory()

    def migrate_to_current(self, database_path: Path, current_version: int) -> int:
        if current_version > ANALYTICS_SCHEMA_VERSION:
            raise RuntimeError(
                f"Schema analytics v{current_version} lebih baru dari aplikasi "
                f"(v{ANALYTICS_SCHEMA_VERSION})."
            )
        version = current_version
        while version < ANALYTICS_SCHEMA_VERSION:
            if version == 1:
                self._migrate_v1_to_v2(database_path)
                version = 2
                continue
            if version == 2:
                self._migrate_v2_to_v3(database_path)
                version = 3
                continue
            if version == 3:
                self._migrate_v3_to_v4(database_path)
                version = 4
                continue
            if version == 4:
                self._migrate_v4_to_v5(database_path)
                version = 5
                continue
            raise RuntimeError(
                f"Migration analytics dari schema v{version} tidak tersedia."
            )
        return version

    def _migrate_v4_to_v5(self, database_path: Path) -> None:
        from shared.attendance_ot.backup import verified_backup

        verified_backup(database_path, "before-v5")
        with self.factory.connect(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("ALTER TABLE employee_records ADD COLUMN division TEXT")
            connection.execute("ALTER TABLE employee_records ADD COLUMN job_title TEXT")
            connection.execute("ALTER TABLE employee_snapshots ADD COLUMN division TEXT")
            connection.execute("ALTER TABLE employee_snapshots ADD COLUMN job_title TEXT")
            connection.execute("ALTER TABLE enriched_attendance ADD COLUMN division TEXT")
            connection.execute("ALTER TABLE enriched_attendance ADD COLUMN job_title TEXT")
            rows = connection.execute(
                "SELECT employee_record_id, organization_json FROM employee_records"
            ).fetchall()
            for row in rows:
                try:
                    organization = json.loads(row["organization_json"] or "{}")
                except (TypeError, ValueError):
                    organization = {}
                division = self._first_organization_value(
                    organization,
                    "business desc",
                    "bus. desc.",
                    "bus. desc",
                    "bus desc",
                )
                job_title = self._first_organization_value(
                    organization,
                    "jobcd desc",
                    "jobcd desc.",
                    "job code desc",
                    "job description",
                )
                connection.execute(
                    "UPDATE employee_records SET division=?, job_title=? "
                    "WHERE employee_record_id=?",
                    (division, job_title, row["employee_record_id"]),
                )
            connection.execute(
                "ALTER TABLE analytics_monthly_employee "
                "RENAME TO analytics_monthly_employee_v4"
            )
            connection.execute(
                """
                CREATE TABLE analytics_monthly_employee (
                    year_month TEXT NOT NULL,
                    emplid TEXT NOT NULL,
                    employee_name TEXT NOT NULL DEFAULT '',
                    classification TEXT NOT NULL DEFAULT '',
                    branch TEXT NOT NULL DEFAULT '',
                    department TEXT NOT NULL DEFAULT '',
                    division TEXT NOT NULL DEFAULT '',
                    pay_group TEXT NOT NULL DEFAULT '',
                    total_records INTEGER NOT NULL,
                    late_count INTEGER NOT NULL,
                    total_ot_minutes REAL NOT NULL,
                    ot_amount REAL NOT NULL,
                    meal_ot_amount REAL NOT NULL,
                    PRIMARY KEY (
                        year_month, emplid, employee_name, classification,
                        branch, department, division, pay_group
                    )
                ) WITHOUT ROWID
                """
            )
            connection.execute(
                """
                INSERT INTO analytics_monthly_employee (
                    year_month, emplid, employee_name, classification, branch,
                    department, division, pay_group, total_records, late_count,
                    total_ot_minutes, ot_amount, meal_ot_amount
                )
                SELECT year_month, emplid, employee_name, classification, branch,
                       department, '', pay_group, total_records, late_count,
                       total_ot_minutes, ot_amount, meal_ot_amount
                FROM analytics_monthly_employee_v4
                """
            )
            connection.execute("DROP TABLE analytics_monthly_employee_v4")
            for statement in (
                "CREATE INDEX idx_monthly_employee_class_late ON analytics_monthly_employee (year_month, classification, late_count DESC)",
                "CREATE INDEX idx_monthly_employee_branch_late ON analytics_monthly_employee (year_month, branch, late_count DESC)",
                "CREATE INDEX idx_monthly_employee_department_late ON analytics_monthly_employee (year_month, department, late_count DESC)",
                "CREATE INDEX idx_monthly_employee_division_late ON analytics_monthly_employee (year_month, division, late_count DESC)",
                "CREATE INDEX idx_monthly_employee_pay_group_late ON analytics_monthly_employee (year_month, pay_group, late_count DESC)",
                "CREATE INDEX idx_enriched_attendance_division_date ON enriched_attendance (division, attendance_date)",
            ):
                connection.execute(statement)
            cursor = connection.execute(
                """
                UPDATE analytics_metadata
                SET schema_version=5, last_migrated_at=?, derived_dirty=1
                WHERE metadata_id=1 AND schema_version=4
                """,
                (current_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise sqlite3.DatabaseError("Schema analytics berubah saat migration.")
            connection.execute("PRAGMA user_version=5")

    @staticmethod
    def _first_organization_value(organization: dict, *keys: str) -> str | None:
        for key in keys:
            value = organization.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    def _migrate_v3_to_v4(self, database_path: Path) -> None:
        from shared.attendance_ot.backup import verified_backup

        verified_backup(database_path, "before-v4")
        with self.factory.connect(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""CREATE TABLE analytics_maintenance (
                event_id INTEGER PRIMARY KEY, operation TEXT NOT NULL,
                period_from TEXT, period_to TEXT, deleted_records INTEGER NOT NULL,
                completed_at TEXT NOT NULL, backup_path TEXT
            )""")
            connection.execute(
                "CREATE INDEX idx_attendance_records_date ON attendance_records(date_in)"
            )
            connection.execute(
                "CREATE INDEX idx_enriched_attendance_source ON enriched_attendance(source_id)"
            )
            cursor = connection.execute(
                "UPDATE analytics_metadata SET schema_version=4, last_migrated_at=? WHERE metadata_id=1 AND schema_version=3",
                (current_timestamp(),),
            )
            if cursor.rowcount != 1:
                raise sqlite3.DatabaseError("Schema analytics berubah saat migration.")
            connection.execute("PRAGMA user_version=4")

    def _migrate_v1_to_v2(self, database_path: Path) -> None:
        timestamp = current_timestamp()
        try:
            with self.factory.connect(database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for statement in V1_TO_V2_STATEMENTS:
                    connection.execute(statement)
                cursor = connection.execute(
                    """
                    UPDATE analytics_metadata
                    SET schema_version = 2, last_migrated_at = ?
                    WHERE metadata_id = 1 AND schema_version = 1
                    """,
                    (timestamp,),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.DatabaseError(
                        "Metadata schema analytics berubah saat migration."
                    )
                connection.execute("PRAGMA user_version = 2")
                connection.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Migration analytics v1 ke v2 gagal: {exc}") from exc

    def _migrate_v2_to_v3(self, database_path: Path) -> None:
        timestamp = current_timestamp()
        try:
            with self.factory.connect(database_path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for statement in V2_TO_V3_STATEMENTS:
                    connection.execute(statement)
                cursor = connection.execute(
                    """
                    UPDATE analytics_metadata
                    SET schema_version = 3, last_migrated_at = ?, derived_dirty = 1
                    WHERE metadata_id = 1 AND schema_version = 2
                    """,
                    (timestamp,),
                )
                if cursor.rowcount != 1:
                    raise sqlite3.DatabaseError(
                        "Metadata schema analytics berubah saat migration."
                    )
                connection.execute("PRAGMA user_version = 3")
                connection.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Migration analytics v2 ke v3 gagal: {exc}") from exc
