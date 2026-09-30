"""Transactional enrichment and aggregate rebuild for Attendance & OT."""

from __future__ import annotations

import re
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


@dataclass(frozen=True, slots=True)
class _Rule:
    code: str
    scheduled_in: str | None
    scheduled_out: str | None


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
        timestamp = current_timestamp()
        inserted = 0
        aggregate_rows = 0
        try:
            with self.factory.connect(database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                if full_rebuild:
                    connection.execute("DELETE FROM analytics_monthly_employee")
                    connection.execute("DELETE FROM enriched_attendance")
                    self._rebuild_employee_snapshots(connection)
                    self._rebuild_schedule_master(connection)
                    where_sql = ""
                    parameters: tuple[object, ...] = ()
                else:
                    ids = sorted(attendance_source_ids or ())
                    if not ids:
                        full_rebuild = True
                        connection.execute("DELETE FROM analytics_monthly_employee")
                        connection.execute("DELETE FROM enriched_attendance")
                        self._rebuild_employee_snapshots(connection)
                        self._rebuild_schedule_master(connection)
                        where_sql = ""
                        parameters = ()
                    else:
                        placeholders = ",".join("?" for _ in ids)
                        connection.execute(
                            f"DELETE FROM enriched_attendance WHERE source_id IN ({placeholders})",
                            ids,
                        )
                        where_sql = f"WHERE a.source_id IN ({placeholders})"
                        parameters = tuple(ids)

                rules = self._load_rules(connection)
                cursor = connection.execute(
                    self._resolution_query(where_sql), parameters
                )
                while True:
                    rows = cursor.fetchmany(self.batch_size)
                    if not rows:
                        break
                    values = [self._enriched_row(row, rules, timestamp) for row in rows]
                    connection.executemany(self._enriched_insert_sql(), values)
                    inserted += len(values)

                connection.execute("DELETE FROM analytics_monthly_employee")
                connection.execute(
                    """
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
                    GROUP BY substr(attendance_date, 1, 7), emplid,
                             COALESCE(employee_name, ''), COALESCE(classification, ''),
                             COALESCE(branch, ''), COALESCE(department, ''),
                             COALESCE(division, ''), COALESCE(pay_group, '')
                    """
                )
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
        return EnrichmentResult(inserted, aggregate_rows, full_rebuild)

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
    def _resolution_query(where_sql: str) -> str:
        return f"""
            SELECT
                a.attendance_record_id, a.source_id, a.emplid, a.date_in,
                a.time_in, a.time_out, a.overtime_hour, a.overtime_minute,
                a.ot_amount, a.meal_ot_amount,
                es.employee_snapshot_id, es.name AS employee_name,
                es.pay_group, es.location_descr AS branch,
                es.classification, es.dept_desc AS department,
                es.division, es.job_title,
                sr.schedule_record_id, sr.schedule_id, sr.schedule_descr,
                sr.effdt AS schedule_effdt
            FROM attendance_records a
            LEFT JOIN employee_snapshots es
              ON es.employee_snapshot_id = (
                SELECT candidate.employee_snapshot_id
                FROM employee_snapshots candidate
                WHERE candidate.emplid = a.emplid
                  AND candidate.snapshot_date <= date(a.date_in)
                ORDER BY candidate.snapshot_date DESC,
                         candidate.employee_snapshot_id DESC
                LIMIT 1
              )
            LEFT JOIN schedule_records sr
              ON sr.schedule_record_id = (
                SELECT candidate.schedule_record_id
                FROM schedule_records candidate
                WHERE candidate.emplid = a.emplid
                  AND candidate.effdt <= substr(a.date_in, 1, 10)
                  AND (
                      candidate.end_effdt IS NULL
                      OR trim(candidate.end_effdt) = ''
                      OR candidate.end_effdt >= substr(a.date_in, 1, 10)
                  )
                ORDER BY candidate.effdt DESC,
                         candidate.schedule_record_id DESC
                LIMIT 1
              )
            {where_sql}
            ORDER BY a.attendance_record_id
        """

    def _enriched_row(
        self, row, rules: dict[str, _Rule], timestamp: str
    ) -> tuple[object, ...]:
        attendance_date = self._date_value(row["date_in"])
        classification = row["classification"]
        resolved = self._resolve_schedule(
            attendance_date,
            row["schedule_record_id"],
            row["schedule_id"],
            row["schedule_descr"],
            classification,
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
        return (
            row["attendance_record_id"],
            row["source_id"],
            row["emplid"],
            attendance_date.isoformat()
            if attendance_date
            else str(row["date_in"] or ""),
            row["time_in"],
            row["time_out"],
            row["employee_snapshot_id"],
            row["employee_name"],
            row["pay_group"],
            row["branch"],
            classification,
            row["department"],
            row["schedule_record_id"],
            row["schedule_id"],
            row["schedule_descr"],
            row["schedule_effdt"],
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
            row["division"],
            row["job_title"],
        )

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
            + ",".join("?" for _ in range(30))
            + ")"
        )

    @staticmethod
    def _normalize_key(value: object) -> str:
        return " ".join(str(value or "").strip().upper().split())

    @staticmethod
    def _date_value(value: object) -> date | None:
        try:
            return parse_date_value(value)
        except ValueError:
            return None

    @staticmethod
    def _clock(value: object) -> time | None:
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
