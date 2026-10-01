"""Bounded read models and a single filter contract for GUI and exports."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date


STATUSES = ("ON_TIME", "LATE", "OFF_DAY", "NO_SCHEDULE", "UNMAPPED_SCHEDULE")
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
DETAIL_COLUMNS = (
    "pay_group",
    "emplid",
    "employee_name",
    "date_in",
    "date_out",
    "actual_time_in",
    "actual_time_out",
    "late_status",
    "late_minutes",
    "job_title",
    "branch",
    "department",
    "resolved_schedule_id",
    "resolved_schedule_descr",
    "overtime_hour",
    "overtime_minute",
    "ot_amount",
    "meal_ot_amount",
    "source_file",
)
DETAIL_LABELS = (
    "Pay Group",
    "EMPLID",
    "Name",
    "Date In",
    "Date Out",
    "Actual In",
    "Actual Out",
    "Attendance Status",
    "Late Minutes",
    "Jabatan",
    "Branch",
    "Department",
    "Schedule ID",
    "Schedule Descr",
    "Overtime Hour",
    "Overtime Minute",
    "OT Amount",
    "Meal OT Amount",
    "Source File",
)
MASTER_COLUMNS = {
    "Employee Snapshot": (
        "pay_group",
        "empl_status",
        "emplid",
        "name",
        "location_descr",
        "dept_desc",
        "division",
        "job_title",
        "regional",
        "last_seen_period",
        "source_status",
        "source_file",
        "source_sheet",
        "source_row",
    ),
    "Employee Monthly Count": (
        "snapshot_period",
        "employee_count",
    ),
    "Schedule Assignment": (
        "assignment_status",
        "emplid",
        "schedule_id",
        "schedule_descr",
        "effdt",
        "end_effdt",
        "rotation",
        "last_seen_period",
        "source_file",
        "source_sheet",
        "source_row",
    ),
    "Schedule Rule": (
        "schedule_rule_id",
        "schedule_id",
        "schedule_descr",
        "rule_code",
        "scheduled_in",
        "scheduled_out",
        "weekdays",
        "priority",
        "is_builtin",
        "source_file",
        "rule_text",
    ),
}
SOURCE_COLUMNS = (
    "filename",
    "source_type",
    "row_count",
    "status",
    "imported_at",
    "source_path",
    "error_detail",
)


@dataclass(frozen=True)
class AnalyticsFilters:
    period: str = ""
    date_from: str = ""
    date_to: str = ""
    branches: tuple[str, ...] = ()
    pay_groups: tuple[str, ...] = ()
    departments: tuple[str, ...] = ()
    divisions: tuple[str, ...] = ()
    search: str = ""
    status: str = ""
    classification: str = ""
    emplid: str = ""

    def __post_init__(self):
        if self.period:
            if len(self.period) not in (4, 7):
                raise ValueError("Period: YYYY atau YYYY-MM.")
            date.fromisoformat(
                self.period + ("-01-01" if len(self.period) == 4 else "-01")
            )
        for value in (self.date_from, self.date_to):
            if value:
                date.fromisoformat(value)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Date From harus <= Date To.")
        if self.status and self.status not in STATUSES:
            raise ValueError("Attendance Status tidak valid.")
        if self.classification not in ("", "HO", "BRANCH"):
            raise ValueError("Classification tidak valid.")

    def describe(self):
        return (
            "; ".join(
                f"{key}: {', '.join(value) if isinstance(value, tuple) else value}"
                for key, value in vars(self).items()
                if value
            )
            or "All Data"
        )

    def sql(self, *, monthly=False, alias=""):
        prefix = alias + "." if alias else ""
        clauses, values = [], []
        time_col = prefix + ("year_month" if monthly else "attendance_date")
        if self.period:
            clauses.append(f"{time_col} >= ? AND {time_col} < ?")
            year = int(self.period[:4])
            if len(self.period) == 4:
                low, high = f"{year:04d}-01", f"{year + 1:04d}-01"
            else:
                month = int(self.period[5:7])
                low = self.period
                high = f"{year + (month == 12):04d}-{month % 12 + 1:02d}"
            values.extend(
                (low if monthly else low + "-01", high if monthly else high + "-01")
            )
        for column, operator, value in (
            (time_col, ">=", self.date_from),
            (time_col, "<=", self.date_to),
            (prefix + "late_status", "=", self.status),
            (prefix + "classification", "=", self.classification),
            (prefix + "emplid", "=", self.emplid),
        ):
            if value:
                clauses.append(f"{column} {operator} ?")
                values.append(value)
        for column, choices in (
            ("branch", self.branches),
            ("pay_group", self.pay_groups),
            ("department", self.departments),
            ("division", self.divisions),
        ):
            if choices:
                clauses.append(
                    f"{prefix}{column} IN ({','.join('?' for _ in choices)})"
                )
                values.extend(choices)
        if self.search:
            # instr treats %, _ and quotes literally; identifiers remain text.
            clauses.append(
                f"(instr(lower({prefix}emplid), lower(?)) > 0 OR instr(lower(COALESCE({prefix}employee_name,'')), lower(?)) > 0)"
            )
            values.extend((self.search, self.search))
        return " AND ".join(clauses) or "1=1", tuple(values)


@dataclass(frozen=True)
class PageResult:
    items: tuple[dict, ...]
    total: int
    offset: int
    limit: int


class ReportingSession:
    """All reads in a session share one SQLite snapshot (also used by export)."""

    def __init__(self, connection):
        self.connection = connection

    def relation(self, filters):
        monthly = not (filters.date_from or filters.date_to or filters.status)
        where, args = filters.sql(monthly=monthly)
        if monthly:
            sql = f"SELECT year_month, emplid, employee_name, classification, branch, department, division, pay_group, total_records, late_count, total_ot_minutes, ot_amount, meal_ot_amount FROM analytics_monthly_employee WHERE {where}"
        else:
            sql = f"SELECT substr(attendance_date,1,7) year_month, emplid, employee_name, classification, branch, department, division, pay_group, 1 total_records, CASE WHEN late_status='LATE' THEN 1 ELSE 0 END late_count, total_ot_minutes, ot_amount, meal_ot_amount FROM enriched_attendance WHERE {where}"
        return sql, args

    def dashboard(self, filters):
        sql, args = self.relation(filters)
        row = self.connection.execute(
            f"""WITH filtered AS ({sql})
            SELECT COALESCE(SUM(total_records),0) records, COUNT(DISTINCT emplid) employees,
            COALESCE(SUM(late_count),0) late_records, COALESCE(SUM(total_ot_minutes),0)/60.0 ot_hours,
            COALESCE(SUM(ot_amount),0) ot_amount, COALESCE(SUM(meal_ot_amount),0) meal_amount FROM filtered""",
            args,
        ).fetchone()
        rankings = {}
        for key, dims, condition in (
            (
                "HO Employees",
                "emplid, MAX(employee_name) employee_name",
                "classification='HO'",
            ),
            (
                "BRANCH Employees",
                "emplid, MAX(employee_name) employee_name",
                "classification='BRANCH'",
            ),
            (
                "Branches",
                "branch",
                "classification='BRANCH' AND COALESCE(branch,'')<>''",
            ),
            (
                "HO Departments",
                "department",
                "classification='HO' AND COALESCE(department,'')<>''",
            ),
        ):
            group = dims.split(",")[0]
            rankings[key] = tuple(
                dict(r)
                for r in self.connection.execute(
                    f"""WITH filtered AS ({sql})
                SELECT {dims}, SUM(late_count) late_count FROM filtered WHERE {condition}
                GROUP BY {group} HAVING SUM(late_count)>0 ORDER BY late_count DESC, {group} LIMIT 5""",
                    args,
                )
            )
        return {"kpi": dict(row), "rankings": rankings}

    def detail_sql(self, filters):
        where, args = filters.sql(alias="e")
        raw_fields = {"date_in", "date_out", "source_file"}
        fields = ", ".join(
            f"a.{column} AS {column}"
            if column in raw_fields
            else f"e.{column}"
            for column in DETAIL_COLUMNS
        )
        return (
            f"SELECT {fields} FROM enriched_attendance e JOIN attendance_records a ON a.attendance_record_id=e.attendance_record_id WHERE {where} ORDER BY e.attendance_date, e.attendance_record_id",
            args,
        )

    def details(self, filters, limit=200, offset=0):
        limit, offset = self._bounds(limit, offset)
        where, args = filters.sql()
        total = self.connection.execute(
            f"SELECT COUNT(*) FROM enriched_attendance WHERE {where}", args
        ).fetchone()[0]
        sql, args = self.detail_sql(filters)
        items = tuple(
            dict(r)
            for r in self.connection.execute(
                sql + " LIMIT ? OFFSET ?", args + (limit, offset)
            )
        )
        return PageResult(items, total, offset, limit)

    def matrix_sql(self, filters, year):
        if not 1 <= int(year) <= 9999:
            raise ValueError("Year tidak valid.")
        sql, args = self.relation(filters)
        months = ",".join(
            f"SUM(CASE WHEN substr(year_month,6,2)='{i:02d}' THEN late_count ELSE 0 END) AS {name}"
            for i, name in enumerate(MONTHS, 1)
        )
        return (
            f"""WITH filtered AS ({sql}) SELECT classification,
            CASE WHEN classification='HO' THEN COALESCE(department,'') ELSE COALESCE(branch,'') END group_name,
            emplid, MAX(employee_name) employee_name, {months}, SUM(late_count) Total
            FROM filtered WHERE year_month>=? AND year_month<?
            GROUP BY classification, group_name, emplid HAVING SUM(late_count)>0
            ORDER BY classification, group_name, emplid""",
            args + (f"{int(year):04d}-01", f"{int(year) + 1:04d}-01"),
        )

    def matrix(self, filters, year, limit=200, offset=0):
        limit, offset = self._bounds(limit, offset)
        sql, args = self.matrix_sql(filters, year)
        total = self.connection.execute(
            f"SELECT COUNT(*) FROM ({sql})", args
        ).fetchone()[0]
        return PageResult(
            tuple(
                dict(r)
                for r in self.connection.execute(
                    sql + " LIMIT ? OFFSET ?", args + (limit, offset)
                )
            ),
            total,
            offset,
            limit,
        )

    def master(self, kind, search="", limit=200, offset=0):
        limit, offset = self._bounds(limit, offset)
        columns = MASTER_COLUMNS[kind]
        if kind == "Employee Snapshot":
            table = """
                (WITH latest_source AS (
                    SELECT source_id FROM source_registry
                    WHERE source_type='EMPLOYEE' AND imported_at IS NOT NULL
                      AND status<>'ERROR'
                    ORDER BY imported_at DESC, source_id DESC LIMIT 1
                ), ranked AS (
                    SELECT e.*,
                           substr(COALESCE(date(e.snapshot_date), r.imported_at),1,7)
                               AS last_seen_period,
                           e.status AS source_status,
                           MAX(CASE WHEN e.source_id=(SELECT source_id FROM latest_source)
                               THEN 1 ELSE 0 END) OVER (PARTITION BY e.emplid)
                               AS present_latest,
                           ROW_NUMBER() OVER (
                               PARTITION BY e.emplid
                               ORDER BY COALESCE(date(e.snapshot_date),
                                                 date(r.imported_at),
                                                 '0001-01-01') DESC,
                                        r.imported_at DESC, e.employee_record_id DESC
                           ) AS current_rank
                    FROM employee_records e
                    JOIN source_registry r ON r.source_id=e.source_id
                )
                SELECT pay_group,
                       CASE WHEN present_latest=1 THEN 'ACTIVE' ELSE 'INACTIVE' END
                           AS empl_status,
                       emplid, name, location_descr, dept_desc, division,
                       job_title, regional, last_seen_period, source_status,
                       source_file, source_sheet, source_row
                FROM ranked WHERE current_rank=1)
            """
            order = "emplid"
            search_columns = (
                "emplid",
                "name",
                "pay_group",
                "location_descr",
                "dept_desc",
                "division",
                "job_title",
            )
            fields = ",".join(columns)
        elif kind == "Schedule Assignment":
            table = """
                (WITH ranked AS (
                    SELECT s.*,
                           substr(r.imported_at,1,7) AS last_seen_period,
                           COUNT(*) OVER (
                               PARTITION BY s.emplid, COALESCE(s.effdt,'')
                           ) AS effdt_count,
                           CASE
                               WHEN date(s.effdt)>date('now') THEN 'SCHEDULED'
                               WHEN s.end_effdt IS NOT NULL
                                    AND trim(s.end_effdt)<>''
                                    AND date(s.end_effdt)<date('now') THEN 'EXPIRED'
                               ELSE 'ACTIVE'
                           END AS assignment_status,
                           ROW_NUMBER() OVER (
                               PARTITION BY s.emplid
                               ORDER BY
                                 CASE
                                   WHEN date(s.effdt)<=date('now') AND
                                        (s.end_effdt IS NULL OR trim(s.end_effdt)=''
                                         OR date(s.end_effdt)>=date('now')) THEN 0
                                   WHEN date(s.effdt)>date('now') THEN 1 ELSE 2
                                 END,
                                 CASE WHEN date(s.effdt)>date('now')
                                      THEN date(s.effdt) END ASC,
                                 date(s.effdt) DESC,
                                 s.schedule_record_id DESC
                           ) AS current_rank
                    FROM schedule_records s
                    JOIN source_registry r ON r.source_id=s.source_id
                )
                SELECT CASE WHEN effdt_count>1 THEN 'CONFLICT'
                            ELSE assignment_status END AS assignment_status,
                       emplid, schedule_id, schedule_descr,
                       effdt, end_effdt, rotation, last_seen_period,
                       source_file, source_sheet, source_row
                FROM ranked WHERE current_rank=1)
            """
            order = "emplid"
            search_columns = ("emplid", "schedule_id", "schedule_descr")
            fields = ",".join(columns)
        elif kind == "Employee Monthly Count":
            table = """
                (SELECT substr(COALESCE(date(e.snapshot_date), r.imported_at),1,7)
                            AS snapshot_period,
                        COUNT(DISTINCT e.emplid) AS employee_count
                 FROM employee_records e
                 JOIN source_registry r ON r.source_id=e.source_id
                 GROUP BY snapshot_period)
            """
            order = "snapshot_period DESC"
            search_columns = ("snapshot_period",)
            fields = ",".join(columns)
        else:
            table = "schedule_rule_master m LEFT JOIN schedule_rule_records r ON r.schedule_rule_record_id=m.source_schedule_rule_record_id"
            order = "m.schedule_rule_id"
            search_columns = ("m.schedule_id", "m.schedule_descr", "r.rule_text")
            fields = ",".join(
                ("r." if c in ("source_file", "rule_text") else "m.") + c
                for c in columns
            )
        where = (
            " OR ".join(
                f"instr(lower(COALESCE({c},'')),lower(?))>0" for c in search_columns
            )
            if search
            else "1=1"
        )
        args = (search,) * len(search_columns) if search else ()
        total = self.connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", args
        ).fetchone()[0]
        items = tuple(
            dict(r)
            for r in self.connection.execute(
                f"SELECT {fields} FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
                args + (limit, offset),
            )
        )
        return PageResult(items, total, offset, limit)

    def options(self):
        return {
            name: tuple(
                row[0]
                for row in self.connection.execute(
                    f"SELECT DISTINCT {column} FROM analytics_monthly_employee WHERE {column}<>'' ORDER BY {column}"
                )
            )
            for name, column in (
                ("periods", "year_month"),
                ("branches", "branch"),
                ("pay_groups", "pay_group"),
                ("departments", "department"),
                ("divisions", "division"),
            )
        }

    def sources(self, limit=200, offset=0):
        limit, offset = self._bounds(limit, offset)
        total = self.connection.execute(
            "SELECT COUNT(*) FROM source_registry"
        ).fetchone()[0]
        items = tuple(
            dict(r)
            for r in self.connection.execute(
                f"SELECT source_id, {','.join(SOURCE_COLUMNS)} FROM source_registry ORDER BY source_type, filename, source_id LIMIT ? OFFSET ?",
                (limit, offset),
            )
        )
        return PageResult(items, total, offset, limit)

    def stream(self, sql, args=(), batch_size=1000):
        cursor = self.connection.execute(sql, args)
        while rows := cursor.fetchmany(batch_size):
            yield from rows

    @staticmethod
    def _bounds(limit, offset):
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("Pagination tidak valid (limit 1..1000, offset >= 0).")
        return limit, offset


class ReportingQueries:
    @contextmanager
    def snapshot(self, *, allow_dirty=False):
        with self.factory.connect(self._database(), read_only=True) as connection:
            connection.execute("BEGIN")
            metadata = connection.execute(
                "SELECT derived_dirty FROM analytics_metadata WHERE metadata_id=1"
            ).fetchone()
            if metadata[0] and not allow_dirty:
                raise RuntimeError(
                    "Analytics perlu Refresh Data sebelum ditampilkan atau diekspor."
                )
            yield ReportingSession(connection)

    def view(
        self,
        filters=AnalyticsFilters(),
        *,
        tab="Dashboard",
        offset=0,
        year=None,
        master_kind="Employee Snapshot",
        master_search="",
    ):
        with self.snapshot(
            allow_dirty=tab in ("Source Files", "Master Data")
        ) as session:
            if tab == "Dashboard":
                return session.dashboard(filters)
            if tab == "Detail Data":
                return session.details(filters, offset=offset)
            if tab == "Data Terlambat":
                return session.matrix(filters, year or date.today().year, offset=offset)
            if tab == "Master Data":
                return session.master(master_kind, master_search, offset=offset)
            if tab == "Source Files":
                return session.sources(offset=offset)
            raise ValueError("Tab tidak dikenal.")

    def filter_options(self):
        with self.snapshot() as session:
            return session.options()
