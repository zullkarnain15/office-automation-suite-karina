"""Transactional enrichment and aggregate rebuild for Attendance & OT."""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

from shared.attendance_ot.models import EnrichmentResult
from shared.attendance_ot.readers import parse_date_value, parse_time_value
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp

_TIME_RANGE = re.compile(
    r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)\s*[-–—]\s*"
    r"([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)"
)
_TIMELESS_SNAPSHOT_DATE = "0001-01-01"
_BULK_REINDEX_THRESHOLD = 25_000


@dataclass(frozen=True, slots=True)
class _Rule:
    code: str
    scheduled_in: str | None
    scheduled_out: str | None


@dataclass(frozen=True, slots=True)
class _Timeline:
    """Rows ordered by their ISO effective date for O(log n) lookup."""

    dates: tuple[str, ...]
    rows: tuple[object, ...]


class AttendanceOTEnrichmentService:
    """Resolve raw rows in bounded batches and atomically refresh aggregates."""

    def __init__(
        self,
        *,
        batch_size: int = 1_000,
        factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        self.batch_size = batch_size
        self.factory = factory or SQLiteConnectionFactory()

    def rebuild(
        self,
        database: Path,
        *,
        full_rebuild: bool = True,
        attendance_source_ids: set[int] | None = None,
    ) -> EnrichmentResult:
        try:
            with self.factory.connect(database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                result = self.rebuild_connection(
                    connection,
                    full_rebuild=full_rebuild,
                    attendance_source_ids=attendance_source_ids,
                )
                connection.commit()
        except Exception as exc:
            with self.factory.connect(database) as connection:
                connection.execute(
                    """
                    UPDATE analytics_metadata
                    SET derived_dirty=1, derived_error=? WHERE metadata_id=1
                    """,
                    (str(exc)[:2000],),
                )
            raise
        return result

    def rebuild_connection(
        self,
        connection,
        *,
        full_rebuild: bool = True,
        attendance_source_ids: set[int] | None = None,
        employee_scope: dict[str, str] | None = None,
        additional_impacted_months: set[str] | None = None,
    ) -> EnrichmentResult:
        """Rebuild derived rows inside an existing caller-owned transaction."""

        timestamp = current_timestamp()
        inserted = 0
        index_definitions: tuple[tuple[str, str], ...] = ()
        impacted_months: set[str] | None = None
        additional_impacted_months = {
            str(month)
            for month in (additional_impacted_months or ())
            if str(month).strip()
        }
        ids = sorted(attendance_source_ids or ())
        employee_scope = {
            str(emplid): str(from_date)
            for emplid, from_date in (employee_scope or {}).items()
            if str(emplid).strip()
        }
        if not full_rebuild and not ids and not employee_scope:
            full_rebuild = True
        employee_scope_prepared = False
        if not full_rebuild and employee_scope and not ids:
            self._prepare_employee_scope(connection, employee_scope)
            employee_scope_prepared = True
            raw_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM attendance_records"
                ).fetchone()[0]
            )
            scoped_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM attendance_records a
                    WHERE EXISTS (
                        SELECT 1 FROM temp.rebuild_employee_scope scope
                        WHERE scope.emplid=a.emplid
                          AND substr(a.date_in, 1, 10)>=scope.from_date
                    )
                    """
                ).fetchone()[0]
            )
            # Once a change covers most of a large database, the optimized full
            # rebuild is faster because reporting indexes are recreated in bulk.
            if (
                raw_count >= _BULK_REINDEX_THRESHOLD
                and scoped_count * 2 >= raw_count
            ):
                full_rebuild = True
                employee_scope = {}
        if full_rebuild:
            # Maintaining every reporting index row-by-row makes a multi-million
            # row rebuild dramatically slower.  SQLite restores dropped indexes
            # if this transaction rolls back; on success they are recreated once
            # after the bulk load.
            raw_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM attendance_records"
                ).fetchone()[0]
            )
            if raw_count >= _BULK_REINDEX_THRESHOLD:
                index_definitions = self._drop_enriched_indexes(connection)
            connection.execute("DELETE FROM analytics_monthly_employee")
            connection.execute("DELETE FROM enriched_attendance")
            self._rebuild_employee_snapshots(connection)
            self._rebuild_schedule_master(connection)
            where_sql = ""
            parameters: tuple[object, ...] = ()
        else:
            impacted_months = set(additional_impacted_months)
            if employee_scope and not employee_scope_prepared:
                self._prepare_employee_scope(connection, employee_scope)
            predicates: list[str] = []
            parameters_list: list[object] = []
            if ids:
                placeholders = ",".join("?" for _ in ids)
                predicates.append(f"source_id IN ({placeholders})")
                parameters_list.extend(ids)
            if employee_scope:
                predicates.append(
                    "EXISTS (SELECT 1 FROM temp.rebuild_employee_scope scope "
                    "WHERE scope.emplid=enriched_attendance.emplid "
                    "AND enriched_attendance.attendance_date>=scope.from_date)"
                )
            delete_where = " OR ".join(predicates)
            parameters = tuple(parameters_list)
            impacted_months.update(
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT substr(attendance_date, 1, 7) "
                    f"FROM enriched_attendance WHERE {delete_where}",
                    parameters,
                )
                if row[0]
            )
            connection.execute(
                f"DELETE FROM enriched_attendance WHERE {delete_where}",
                parameters,
            )
            if employee_scope:
                self._sync_employee_snapshots(connection)
            attendance_predicates: list[str] = []
            if ids:
                placeholders = ",".join("?" for _ in ids)
                attendance_predicates.append(f"a.source_id IN ({placeholders})")
            if employee_scope:
                attendance_predicates.append(
                    "EXISTS (SELECT 1 FROM temp.rebuild_employee_scope scope "
                    "WHERE scope.emplid=a.emplid "
                    "AND substr(a.date_in, 1, 10)>=scope.from_date)"
                )
            where_sql = "WHERE " + " OR ".join(attendance_predicates)

        rules = self._load_rules(connection)
        employee_timelines = self._employee_timelines(connection)
        schedule_timelines = self._schedule_timelines(connection)
        latest_master_employees = self._latest_master_employees(connection)
        cursor = connection.execute(self._attendance_query(where_sql), parameters)
        while True:
            rows = cursor.fetchmany(max(self.batch_size, 10_000))
            if not rows:
                break
            values = [
                self._enriched_row(
                    row,
                    rules,
                    timestamp,
                    employee_timelines,
                    schedule_timelines,
                    latest_master_employees,
                )
                for row in rows
            ]
            connection.executemany(self._enriched_insert_sql(), values)
            inserted += len(values)
            if impacted_months is not None:
                impacted_months.update(
                    str(value[3])[:7] for value in values if value[3]
                )

        self._rebuild_monthly_aggregate(
            connection,
            impacted_months,
            employee_scoped=bool(employee_scope) and not ids,
        )
        if index_definitions:
            self._restore_indexes(connection, index_definitions)
        aggregate_rows = int(
            connection.execute(
                "SELECT COUNT(*) FROM analytics_monthly_employee"
            ).fetchone()[0]
        )
        connection.execute(
            """
            UPDATE analytics_metadata
            SET derived_dirty=0, derived_refreshed_at=?, derived_error=NULL
            WHERE metadata_id=1
            """,
            (timestamp,),
        )
        return EnrichmentResult(inserted, aggregate_rows, full_rebuild)

    @staticmethod
    def _rebuild_monthly_aggregate(
        connection,
        impacted_months: set[str] | None,
        *,
        employee_scoped: bool = False,
    ) -> None:
        parameters: tuple[object, ...] = ()
        where_sql = ""
        if impacted_months is None:
            connection.execute("DELETE FROM analytics_monthly_employee")
        elif employee_scoped:
            scope_match = (
                "EXISTS (SELECT 1 FROM temp.rebuild_employee_scope scope "
                "WHERE scope.emplid=analytics_monthly_employee.emplid "
                "AND analytics_monthly_employee.year_month"
                ">=substr(scope.from_date, 1, 7))"
            )
            connection.execute(
                f"DELETE FROM analytics_monthly_employee WHERE {scope_match}"
            )
            where_sql = (
                "WHERE EXISTS (SELECT 1 FROM temp.rebuild_employee_scope scope "
                "WHERE scope.emplid=enriched_attendance.emplid "
                "AND enriched_attendance.attendance_date>=scope.from_date)"
            )
        elif impacted_months:
            months = tuple(sorted(impacted_months))
            placeholders = ",".join("?" for _ in months)
            connection.execute(
                "DELETE FROM analytics_monthly_employee "
                f"WHERE year_month IN ({placeholders})",
                months,
            )
            where_sql = f"WHERE substr(attendance_date, 1, 7) IN ({placeholders})"
            parameters = months
        else:
            return
        connection.execute(
            f"""
            INSERT INTO analytics_monthly_employee (
                year_month, emplid, employee_name, classification,
                branch, department, division, pay_group, total_records,
                late_count, total_ot_minutes, ot_amount, meal_ot_amount
            )
            SELECT
                substr(attendance_date, 1, 7), emplid,
                COALESCE(employee_name, ''), COALESCE(classification, ''),
                COALESCE(branch, ''), COALESCE(department, ''),
                COALESCE(division, ''), COALESCE(pay_group, ''), COUNT(*),
                SUM(CASE WHEN late_status='LATE' THEN 1 ELSE 0 END),
                SUM(total_ot_minutes), SUM(ot_amount), SUM(meal_ot_amount)
            FROM enriched_attendance
            {where_sql}
            GROUP BY substr(attendance_date, 1, 7), emplid,
                     COALESCE(employee_name, ''), COALESCE(classification, ''),
                     COALESCE(branch, ''), COALESCE(department, ''),
                     COALESCE(division, ''), COALESCE(pay_group, '')
            """,
            parameters,
        )

    @staticmethod
    def _prepare_employee_scope(
        connection, employee_scope: dict[str, str]
    ) -> None:
        connection.execute("DROP TABLE IF EXISTS temp.rebuild_employee_scope")
        connection.execute(
            "CREATE TEMP TABLE rebuild_employee_scope ("
            "emplid TEXT PRIMARY KEY, from_date TEXT NOT NULL) WITHOUT ROWID"
        )
        connection.executemany(
            "INSERT INTO rebuild_employee_scope (emplid, from_date) VALUES (?, ?)",
            sorted(employee_scope.items()),
        )
        # The display fallback uses the latest employee snapshot when attendance
        # predates every available snapshot.  Widen those exceptional employees
        # to their first attendance date so a targeted rebuild stays exact.
        connection.execute(
            """
            UPDATE rebuild_employee_scope
            SET from_date = (
                SELECT MIN(substr(a.date_in, 1, 10))
                FROM attendance_records a
                WHERE a.emplid=rebuild_employee_scope.emplid
            )
            WHERE (
                SELECT MIN(substr(a.date_in, 1, 10))
                FROM attendance_records a
                WHERE a.emplid=rebuild_employee_scope.emplid
            ) < COALESCE((
                SELECT MIN(COALESCE(date(e.snapshot_date), ?))
                FROM employee_records e
                WHERE e.emplid=rebuild_employee_scope.emplid
            ), '9999-12-31')
            """,
            (_TIMELESS_SNAPSHOT_DATE,),
        )

    @staticmethod
    def _sync_employee_snapshots(connection) -> None:
        connection.execute(
            """
            DELETE FROM employee_snapshots
            WHERE emplid IN (SELECT emplid FROM rebuild_employee_scope)
              AND NOT EXISTS (
                  SELECT 1 FROM employee_records source
                  WHERE source.employee_record_id=
                        employee_snapshots.source_employee_record_id
              )
            """
        )
        connection.execute(
            """
            INSERT INTO employee_snapshots (
                source_employee_record_id, emplid, snapshot_date, snapshot_period,
                name, pay_group, status, location_descr, regional, dept_desc,
                classification, division, job_title
            )
            SELECT employee_record_id, emplid,
                   COALESCE(date(snapshot_date), ?),
                   substr(COALESCE(date(snapshot_date), ?), 1, 7),
                   name, pay_group, status,
                   location_descr, regional, dept_desc,
                   CASE WHEN upper(
                        replace(replace(replace(
                            trim(replace(replace(replace(
                                COALESCE(location_descr, ''), char(9), ' '
                            ), char(10), ' '), char(13), ' ')),
                            '  ', ' '), '  ', ' '), '  ', ' ')
                        )='HEAD OFFICE'
                        THEN 'HO' ELSE 'BRANCH' END,
                   division, job_title
            FROM employee_records
            WHERE emplid IN (SELECT emplid FROM rebuild_employee_scope)
              AND (snapshot_date IS NULL OR date(snapshot_date) IS NOT NULL)
            ON CONFLICT(source_employee_record_id) DO UPDATE SET
                emplid=excluded.emplid,
                snapshot_date=excluded.snapshot_date,
                snapshot_period=excluded.snapshot_period,
                name=excluded.name,
                pay_group=excluded.pay_group,
                status=excluded.status,
                location_descr=excluded.location_descr,
                regional=excluded.regional,
                dept_desc=excluded.dept_desc,
                classification=excluded.classification,
                division=excluded.division,
                job_title=excluded.job_title
            """,
            (_TIMELESS_SNAPSHOT_DATE, _TIMELESS_SNAPSHOT_DATE),
        )

    @staticmethod
    def _drop_enriched_indexes(connection) -> tuple[tuple[str, str], ...]:
        definitions = tuple(
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='enriched_attendance' "
                "AND sql IS NOT NULL ORDER BY name"
            )
        )
        for name, _sql in definitions:
            connection.execute(f'DROP INDEX "{name.replace(chr(34), chr(34) * 2)}"')
        return definitions

    @staticmethod
    def _restore_indexes(
        connection, definitions: tuple[tuple[str, str], ...]
    ) -> None:
        for _name, sql in definitions:
            connection.execute(sql)

    @staticmethod
    def _rebuild_employee_snapshots(connection) -> None:
        connection.execute("DELETE FROM employee_snapshots")
        connection.execute(
            """
            INSERT INTO employee_snapshots (
                source_employee_record_id, emplid, snapshot_date, snapshot_period,
                name, pay_group, status, location_descr, regional, dept_desc,
                classification, division, job_title
            )
            SELECT employee_record_id, emplid,
                   COALESCE(date(snapshot_date), ?),
                   substr(COALESCE(date(snapshot_date), ?), 1, 7),
                   name, pay_group, status,
                   location_descr, regional, dept_desc,
                   CASE WHEN upper(
                        replace(replace(replace(
                            trim(replace(replace(replace(
                                COALESCE(location_descr, ''), char(9), ' '
                            ), char(10), ' '), char(13), ' ')),
                            '  ', ' '), '  ', ' '), '  ', ' ')
                        )='HEAD OFFICE'
                        THEN 'HO' ELSE 'BRANCH' END,
                   division, job_title
            FROM employee_records
            WHERE snapshot_date IS NULL OR date(snapshot_date) IS NOT NULL
            """,
            (_TIMELESS_SNAPSHOT_DATE, _TIMELESS_SNAPSHOT_DATE),
        )

    def _rebuild_schedule_master(self, connection) -> None:
        connection.execute("DELETE FROM schedule_rule_master")
        builtins = (
            (
                None,
                "__DEFAULT_HO__",
                "DEFAULT HO",
                "Default Schedule HO (fallback)",
                "DEFAULT_HO",
                "08:30",
                "17:30",
                "WD,WE",
                1000,
                1,
            ),
            (
                None,
                "__DEFAULT_BRANCH__",
                "DEFAULT BRANCH",
                "Default Schedule Branch (fallback)",
                "DEFAULT_BRANCH",
                "08:30",
                "16:30",
                "WD,WE",
                1000,
                1,
            ),
            (
                None,
                "WS_HO 3",
                "WS_HO 3",
                "WS_HO 3",
                "EXPLICIT",
                "09:30",
                "18:30",
                "WD,WE",
                100,
                1,
            ),
            (
                None,
                "WS_CCD",
                "WS_CCD",
                "WS_CCD",
                "EXPLICIT",
                "08:30",
                "16:30",
                "WD,WE",
                100,
                1,
            ),
            (
                None,
                "BRANCH OTO",
                "BRANCH OTO",
                "Branch OTO",
                "BRANCH_DEFAULT",
                None,
                None,
                "WD,WE",
                100,
                1,
            ),
            (None, "WD", "WD", "Weekday", "DEFAULT", None, None, "WD", 100, 1),
            (None, "WE", "WE", "Weekend", "DEFAULT", None, None, "WE", 100, 1),
        )
        connection.executemany(
            """
            INSERT INTO schedule_rule_master (
                source_schedule_rule_record_id, schedule_key, schedule_id,
                schedule_descr, rule_code, scheduled_in, scheduled_out,
                weekdays, priority, is_builtin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            builtins,
        )
        rows = connection.execute(
            """
            SELECT schedule_rule_record_id, schedule_id, schedule_descr,
                   rule_text, scheduled_in, scheduled_out, weekdays
            FROM schedule_rule_records ORDER BY schedule_rule_record_id
            """
        ).fetchall()
        values = []
        for row in rows:
            key = self._normalize_key(row["schedule_id"] or row["schedule_descr"])
            if not key:
                key = "__BLANK_BRANCH__"
            scheduled_in = self._clock_text(row["scheduled_in"])
            scheduled_out = self._clock_text(row["scheduled_out"])
            dynamic = self._time_range(
                " ".join(
                    str(value or "")
                    for value in (row["schedule_descr"], row["rule_text"])
                )
            )
            if dynamic and not (scheduled_in and scheduled_out):
                scheduled_in, scheduled_out = dynamic
            text = " ".join(
                str(value or "")
                for value in (
                    row["schedule_id"],
                    row["schedule_descr"],
                    row["rule_text"],
                )
            ).upper()
            if scheduled_in and scheduled_out:
                code = "EXPLICIT"
            elif "BRANCH OTO" in text or not row["schedule_id"]:
                code = "BRANCH_DEFAULT"
            elif "WD" in text or "WE" in text or "DEFAULT" in text:
                code = "DEFAULT"
            else:
                code = "UNMAPPED"
            values.append(
                (
                    row["schedule_rule_record_id"],
                    key,
                    row["schedule_id"],
                    row["schedule_descr"],
                    code,
                    scheduled_in,
                    scheduled_out,
                    row["weekdays"] or "WD,WE",
                    10,
                    0,
                )
            )
        if values:
            connection.executemany(
                """
                INSERT INTO schedule_rule_master (
                    source_schedule_rule_record_id, schedule_key, schedule_id,
                    schedule_descr, rule_code, scheduled_in, scheduled_out,
                    weekdays, priority, is_builtin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    @staticmethod
    def _load_rules(connection) -> dict[str, _Rule]:
        rules: dict[str, _Rule] = {}
        rows = connection.execute(
            """
            SELECT schedule_key, rule_code, scheduled_in, scheduled_out
            FROM schedule_rule_master
            ORDER BY priority DESC, schedule_rule_id DESC
            """
        ).fetchall()
        for row in rows:
            key = str(row["schedule_key"]).upper()
            if key not in rules:
                rules[key] = _Rule(
                    str(row["rule_code"]), row["scheduled_in"], row["scheduled_out"]
                )
        return rules

    @staticmethod
    def _employee_timelines(connection) -> dict[str, _Timeline]:
        grouped: dict[str, tuple[list[str], list[object]]] = {}
        for row in connection.execute(
            """
            SELECT employee_snapshot_id, emplid, snapshot_date, name,
                   pay_group, location_descr, classification, dept_desc,
                   division, job_title
            FROM employee_snapshots
            ORDER BY emplid, snapshot_date, employee_snapshot_id
            """
        ):
            dates, rows = grouped.setdefault(str(row["emplid"]), ([], []))
            dates.append(str(row["snapshot_date"]))
            rows.append(row)
        return {
            emplid: _Timeline(tuple(dates), tuple(rows))
            for emplid, (dates, rows) in grouped.items()
        }

    @staticmethod
    def _schedule_timelines(connection) -> dict[str, _Timeline]:
        grouped: dict[str, tuple[list[str], list[object]]] = {}
        for row in connection.execute(
            """
            SELECT schedule_record_id, emplid, schedule_id, schedule_descr,
                   effdt, end_effdt
            FROM schedule_records
            WHERE effdt IS NOT NULL AND trim(effdt) <> ''
            ORDER BY emplid, effdt, schedule_record_id
            """
        ):
            dates, rows = grouped.setdefault(str(row["emplid"]), ([], []))
            dates.append(str(row["effdt"]))
            rows.append(row)
        return {
            emplid: _Timeline(tuple(dates), tuple(rows))
            for emplid, (dates, rows) in grouped.items()
        }

    @staticmethod
    def _latest_master_employees(connection) -> set[str]:
        latest = connection.execute(
            """
            SELECT source_id FROM source_registry
            WHERE source_type='EMPLOYEE' AND imported_at IS NOT NULL
              AND status<>'ERROR'
            ORDER BY imported_at DESC, source_id DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return set()
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT emplid FROM employee_records WHERE source_id=?",
                (latest[0],),
            )
        }

    @staticmethod
    def _attendance_query(where_sql: str) -> str:
        return f"""
            SELECT
                a.attendance_record_id, a.source_id, a.emplid, a.date_in,
                a.time_in, a.time_out, a.overtime_hour, a.overtime_minute,
                a.ot_amount, a.meal_ot_amount,
                a.name AS source_employee_name,
                a.paylink AS source_pay_group,
                a.job_title AS source_job_title,
                a.location_descr AS source_branch
            FROM attendance_records a
            {where_sql}
            ORDER BY a.attendance_record_id
        """

    def _enriched_row(
        self,
        row,
        rules: dict[str, _Rule],
        timestamp: str,
        employee_timelines: dict[str, _Timeline],
        schedule_timelines: dict[str, _Timeline],
        latest_master_employees: set[str],
    ) -> tuple[object, ...]:
        attendance_date = self._date_value(row["date_in"])
        employee_snapshot, dated_snapshot = self._employee_snapshot(
            employee_timelines.get(str(row["emplid"])), attendance_date
        )
        schedule = self._schedule_record(
            schedule_timelines.get(str(row["emplid"])), attendance_date
        )
        classification = (
            employee_snapshot["classification"] if employee_snapshot else None
        )
        resolved = self._resolve_schedule(
            attendance_date,
            schedule["schedule_record_id"] if schedule else None,
            schedule["schedule_id"] if schedule else None,
            schedule["schedule_descr"] if schedule else None,
            dated_snapshot["classification"] if dated_snapshot else None,
            rules,
        )
        scheduled_in, scheduled_out, workday, late_status = resolved
        late_minutes = 0
        actual = self._clock(row["time_in"])
        scheduled = self._clock(scheduled_in)
        if late_status not in {"OFF_DAY", "NO_SCHEDULE", "UNMAPPED_SCHEDULE"}:
            if actual is None or scheduled is None:
                late_status = "UNMAPPED_SCHEDULE"
            else:
                delta = (
                    actual.hour * 60
                    + actual.minute
                    - scheduled.hour * 60
                    - scheduled.minute
                )
                if delta > 0:
                    late_status = "LATE"
                    late_minutes = delta
                else:
                    late_status = "ON_TIME"
        overtime_hour = float(row["overtime_hour"] or 0)
        overtime_minute = float(row["overtime_minute"] or 0)
        total_ot_minutes = overtime_hour * 60 + overtime_minute
        employee_status = self._employee_status(
            employee_snapshot["employee_snapshot_id"]
            if employee_snapshot
            else None,
            str(row["emplid"]) in latest_master_employees,
        )
        return (
            row["attendance_record_id"],
            row["source_id"],
            row["emplid"],
            attendance_date.isoformat()
            if attendance_date
            else str(row["date_in"] or ""),
            row["time_in"],
            row["time_out"],
            employee_snapshot["employee_snapshot_id"]
            if employee_snapshot
            else None,
            self._preferred_text(
                row["source_employee_name"],
                employee_snapshot["name"] if employee_snapshot else None,
            ),
            self._preferred_text(
                row["source_pay_group"],
                employee_snapshot["pay_group"] if employee_snapshot else None,
            ),
            self._preferred_text(
                row["source_branch"],
                employee_snapshot["location_descr"] if employee_snapshot else None,
            ),
            classification,
            employee_snapshot["dept_desc"] if employee_snapshot else None,
            schedule["schedule_record_id"] if schedule else None,
            schedule["schedule_id"] if schedule else None,
            schedule["schedule_descr"] if schedule else None,
            schedule["effdt"] if schedule else None,
            scheduled_in,
            scheduled_out,
            workday,
            late_status,
            late_minutes,
            overtime_hour,
            overtime_minute,
            total_ot_minutes,
            total_ot_minutes / 60.0,
            float(row["ot_amount"] or 0),
            float(row["meal_ot_amount"] or 0),
            timestamp,
            employee_snapshot["division"] if employee_snapshot else None,
            self._preferred_text(
                row["source_job_title"],
                employee_snapshot["job_title"] if employee_snapshot else None,
            ),
            employee_status,
        )

    @staticmethod
    def _employee_snapshot(
        timeline: _Timeline | None, attendance_date: date | None
    ) -> tuple[object | None, object | None]:
        if timeline is None or not timeline.rows:
            return None, None
        dated = None
        if attendance_date is not None:
            index = bisect_right(timeline.dates, attendance_date.isoformat()) - 1
            if index >= 0:
                dated = timeline.rows[index]
        return dated or timeline.rows[-1], dated

    @staticmethod
    def _schedule_record(
        timeline: _Timeline | None, attendance_date: date | None
    ) -> object | None:
        if timeline is None or attendance_date is None:
            return None
        attendance_text = attendance_date.isoformat()
        index = bisect_right(timeline.dates, attendance_text) - 1
        while index >= 0:
            row = timeline.rows[index]
            end_date = str(row["end_effdt"] or "").strip()
            if not end_date or end_date >= attendance_text:
                return row
            index -= 1
        return None

    def _resolve_schedule(
        self,
        attendance_date: date | None,
        schedule_record_id: int | None,
        schedule_id: str | None,
        schedule_descr: str | None,
        classification: str | None,
        rules: dict[str, _Rule],
    ) -> tuple[str | None, str | None, str | None, str]:
        if attendance_date is None:
            return None, None, None, "UNMAPPED_SCHEDULE"
        workday = (
            "OFF"
            if attendance_date.weekday() == 6
            else ("WE" if attendance_date.weekday() == 5 else "WD")
        )
        default_schedule = self._default_schedule(classification)
        if schedule_record_id is None:
            if default_schedule is None:
                return None, None, workday, "NO_SCHEDULE"
            if workday == "OFF":
                return None, None, workday, "OFF_DAY"
            return (*default_schedule, workday, "ON_TIME")
        key = self._normalize_key(schedule_id)
        descr_key = self._normalize_key(schedule_descr)
        rule = rules.get(key) or rules.get(descr_key)
        if key == "WS_HO 3":
            rule = _Rule("EXPLICIT", "09:30", "18:30")
        elif key == "WS_CCD":
            rule = _Rule("EXPLICIT", "08:30", "16:30")
        if workday == "OFF" and (
            rule
            or default_schedule
            or key in {"WD", "WE", "BRANCH OTO"}
            or not key
        ):
            return None, None, workday, "OFF_DAY"
        if rule and rule.code == "EXPLICIT":
            return rule.scheduled_in, rule.scheduled_out, workday, "ON_TIME"
        dynamic = self._time_range(str(schedule_descr or ""))
        if dynamic:
            return dynamic[0], dynamic[1], workday, "ON_TIME"
        tokens = f"{key} {descr_key}"
        if (
            (classification == "BRANCH" and (not key or "BRANCH OTO" in tokens))
            or (rule and rule.code in {"DEFAULT", "BRANCH_DEFAULT"})
            or any(
                token in tokens.split() for token in ("WD", "WE", "NORMAL", "REGULAR")
            )
        ):
            if classification == "HO":
                return "08:30", "17:30", workday, "ON_TIME"
            if classification == "BRANCH":
                return "08:30", "16:30", workday, "ON_TIME"
        if default_schedule is not None:
            return (*default_schedule, workday, "ON_TIME")
        return None, None, workday, "UNMAPPED_SCHEDULE"

    @staticmethod
    def _default_schedule(classification: str | None) -> tuple[str, str] | None:
        if classification == "HO":
            return "08:30", "17:30"
        if classification == "BRANCH":
            return "08:30", "16:30"
        return None

    @staticmethod
    def _enriched_insert_sql() -> str:
        return (
            "INSERT INTO enriched_attendance VALUES ("
            + ",".join("?" for _ in range(31))
            + ")"
        )

    @staticmethod
    def _preferred_text(primary: object, fallback: object) -> object:
        if primary is not None and str(primary).strip():
            return primary
        return fallback

    @staticmethod
    def _employee_status(snapshot_id: object, present_latest: object) -> str:
        if snapshot_id is None:
            return "Unmapped"
        return "Active" if bool(present_latest) else "Inactive"

    @staticmethod
    def _normalize_key(value: object) -> str:
        return " ".join(str(value or "").strip().upper().split())

    @staticmethod
    def _date_value(value: object) -> date | None:
        if isinstance(value, str):
            text = value.strip()
            if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
                try:
                    return date.fromisoformat(text[:10])
                except ValueError:
                    pass
        try:
            return parse_date_value(value)
        except ValueError:
            return None

    @staticmethod
    def _clock(value: object) -> time | None:
        if isinstance(value, str):
            try:
                return time.fromisoformat(value.strip()).replace(microsecond=0)
            except ValueError:
                pass
        try:
            return parse_time_value(value)
        except ValueError:
            return None

    @classmethod
    def _clock_text(cls, value: object) -> str | None:
        parsed = cls._clock(value)
        return parsed.strftime("%H:%M") if parsed else None

    @staticmethod
    def _time_range(value: str) -> tuple[str, str] | None:
        match = _TIME_RANGE.search(value)
        if not match:
            return None
        return (
            f"{int(match.group(1)):02d}:{match.group(2)}",
            f"{int(match.group(3)):02d}:{match.group(4)}",
        )
