"""Read-only analytics queries prepared for the Sprint 4 presentation layer."""

from __future__ import annotations

from pathlib import Path

from shared.attendance_ot.models import KpiSummary
from shared.attendance_ot.reporting import ReportingQueries
from shared.database.connection_factory import SQLiteConnectionFactory


class AttendanceOTAnalyticsQueryService(ReportingQueries):
    def __init__(
        self,
        storage_service,
        *,
        factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.storage_service = storage_service
        self.factory = factory or SQLiteConnectionFactory()

    def kpi_summary(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> KpiSummary:
        database = self._database()
        where, values = self._period_filter(start_date, end_date)
        with self.factory.connect(database, read_only=True) as connection:
            row = connection.execute(
                f"""
                SELECT COALESCE(SUM(total_records), 0) total_records,
                       COUNT(DISTINCT emplid) distinct_employees,
                       COALESCE(SUM(late_count), 0) late_records,
                       COALESCE(SUM(total_ot_minutes), 0) total_ot_minutes,
                       COALESCE(SUM(ot_amount), 0) ot_amount,
                       COALESCE(SUM(meal_ot_amount), 0) meal_ot_amount
                FROM analytics_monthly_employee {where}
                """,
                values,
            ).fetchone()
        minutes = float(row["total_ot_minutes"])
        return KpiSummary(
            int(row["total_records"]),
            int(row["distinct_employees"]),
            int(row["late_records"]),
            minutes,
            minutes / 60.0,
            float(row["ot_amount"]),
            float(row["meal_ot_amount"]),
        )

    def top_late_employees(
        self,
        classification: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 3,
    ) -> tuple[dict[str, object], ...]:
        if classification not in {"HO", "BRANCH"}:
            raise ValueError("classification must be HO or BRANCH.")
        return self._ranking(
            "emplid, employee_name",
            "classification=?",
            (classification,),
            start_date,
            end_date,
            limit,
        )

    def top3_late_employee_ho(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[dict[str, object], ...]:
        return self.top_late_employees("HO", start_date, end_date, 3)

    def top3_late_employee_branch(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[dict[str, object], ...]:
        return self.top_late_employees("BRANCH", start_date, end_date, 3)

    def top_late_branches(
        self, start_date: str | None = None, end_date: str | None = None, limit: int = 3
    ) -> tuple[dict[str, object], ...]:
        return self._ranking(
            "branch",
            "classification='BRANCH' AND branch<>''",
            (),
            start_date,
            end_date,
            limit,
        )

    def top3_late_branches(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[dict[str, object], ...]:
        return self.top_late_branches(start_date, end_date, 3)

    def top_late_departments_ho(
        self, start_date: str | None = None, end_date: str | None = None, limit: int = 3
    ) -> tuple[dict[str, object], ...]:
        return self._ranking(
            "department",
            "classification='HO' AND department<>''",
            (),
            start_date,
            end_date,
            limit,
        )

    def top3_late_departments_ho(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[dict[str, object], ...]:
        return self.top_late_departments_ho(start_date, end_date, 3)

    def monthly_late_matrix(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> tuple[dict[str, object], ...]:
        database = self._database()
        where, values = self._period_filter(start_date, end_date)
        with self.factory.connect(database, read_only=True) as connection:
            rows = connection.execute(
                f"""
                SELECT year_month, emplid, employee_name, classification,
                       branch, department, pay_group, late_count
                FROM analytics_monthly_employee {where}
                ORDER BY year_month, late_count DESC, emplid
                """,
                values,
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def _ranking(
        self,
        dimensions: str,
        condition: str,
        condition_values: tuple[object, ...],
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> tuple[dict[str, object], ...]:
        if limit <= 0:
            return ()
        period_sql, period_values = self._period_filter(
            start_date, end_date, prefix=True
        )
        database = self._database()
        with self.factory.connect(database, read_only=True) as connection:
            rows = connection.execute(
                f"""
                SELECT {dimensions}, SUM(late_count) AS late_count
                FROM analytics_monthly_employee
                WHERE {condition}{period_sql}
                GROUP BY {dimensions}
                HAVING SUM(late_count) > 0
                ORDER BY late_count DESC, {dimensions}
                LIMIT ?
                """,
                condition_values + period_values + (limit,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def _database(self) -> Path:
        status = self.storage_service.resolve_status()
        if status.database_path is None or not status.database_valid:
            raise RuntimeError("Database analytics belum tersedia.")
        return status.database_path

    @staticmethod
    def _period_filter(
        start_date: str | None, end_date: str | None, *, prefix: bool = False
    ) -> tuple[str, tuple[str, ...]]:
        clauses: list[str] = []
        values: list[str] = []
        if start_date:
            clauses.append("year_month >= ?")
            values.append(start_date[:7])
        if end_date:
            clauses.append("year_month <= ?")
            values.append(end_date[:7])
        if not clauses:
            return "", ()
        joiner = " AND " if prefix else " WHERE "
        return joiner + " AND ".join(clauses), tuple(values)
