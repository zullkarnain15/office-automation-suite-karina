"""SQLite-backed configuration adapter for Att Data Repair."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

from shared.database.connection_factory import SQLiteConnectionFactory
from utilities.att_data_repair.artifacts import AttDataRepairJobRequest
from utilities.att_data_repair.models import AttDataRepairRequest


@dataclass(frozen=True, slots=True)
class AttDataRepairSettings:
    """Typed active settings for Att Data Repair."""

    enabled: bool = True
    minimum_duration_minutes: int = 61
    weekday_default_in: time = time(9, 30)
    weekday_default_out: time = time(17, 0)
    saturday_default_in: time = time(9, 30)
    saturday_default_out: time = time(12, 5)
    saturday_missing_out_default: time = time(11, 0)
    sunday_invalid_default_in: time = time(9, 30)
    sunday_invalid_default_out: time = time(12, 5)
    midnight_time_out_default: time = time(23, 59)
    txt_max_rows: int = 10_000
    generate_txt: bool = True
    generate_excel_report: bool = True
    use_global_period: bool = True
    use_global_output: bool = True


class AttDataRepairConfigurationService:
    """Read active SQLite settings and build engine requests."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def read_settings(self, database_path: str | Path) -> AttDataRepairSettings:
        """Return the singleton Att Data Repair settings row."""

        with self.connection_factory.connect(database_path, read_only=True) as connection:
            row = connection.execute(
                """
                SELECT
                    enabled,
                    minimum_duration_minutes,
                    weekday_default_in,
                    weekday_default_out,
                    saturday_default_in,
                    saturday_default_out,
                    saturday_missing_out_default,
                    sunday_invalid_default_in,
                    sunday_invalid_default_out,
                    midnight_time_out_default,
                    txt_max_rows,
                    generate_txt,
                    generate_excel_report,
                    use_global_period,
                    use_global_output
                FROM att_data_repair_settings
                WHERE att_data_repair_settings_id = 1
                """
            ).fetchone()
        if row is None:
            raise ValueError("Att Data Repair settings singleton tidak ditemukan.")
        return AttDataRepairSettings(
            enabled=bool(row["enabled"]),
            minimum_duration_minutes=int(row["minimum_duration_minutes"]),
            weekday_default_in=_parse_time(row["weekday_default_in"]),
            weekday_default_out=_parse_time(row["weekday_default_out"]),
            saturday_default_in=_parse_time(row["saturday_default_in"]),
            saturday_default_out=_parse_time(row["saturday_default_out"]),
            saturday_missing_out_default=_parse_time(
                row["saturday_missing_out_default"]
            ),
            sunday_invalid_default_in=_parse_time(row["sunday_invalid_default_in"]),
            sunday_invalid_default_out=_parse_time(row["sunday_invalid_default_out"]),
            midnight_time_out_default=_parse_time(
                row["midnight_time_out_default"]
            ),
            txt_max_rows=int(row["txt_max_rows"]),
            generate_txt=bool(row["generate_txt"]),
            generate_excel_report=bool(row["generate_excel_report"]),
            use_global_period=bool(row["use_global_period"]),
            use_global_output=bool(row["use_global_output"]),
        )

    def build_job_request(
        self,
        *,
        settings: AttDataRepairSettings,
        source_report: str | Path,
        period_start: date,
        period_end: date,
        output_root: str | Path,
    ) -> AttDataRepairJobRequest:
        """Map active settings and resolved caller inputs to a job request."""

        self.validate_settings(settings)
        if not settings.enabled:
            raise ValueError("Att Data Repair sedang disabled pada konfigurasi aktif.")
        analysis_request = AttDataRepairRequest(
            source_report=Path(source_report),
            period_start=period_start,
            period_end=period_end,
            minimum_duration_minutes=settings.minimum_duration_minutes,
            weekday_default_in=settings.weekday_default_in,
            weekday_default_out=settings.weekday_default_out,
            saturday_default_in=settings.saturday_default_in,
            saturday_default_out=settings.saturday_default_out,
            saturday_missing_out_default=settings.saturday_missing_out_default,
            sunday_invalid_default_in=settings.sunday_invalid_default_in,
            sunday_invalid_default_out=settings.sunday_invalid_default_out,
            midnight_time_out_default=settings.midnight_time_out_default,
        )
        return AttDataRepairJobRequest(
            analysis_request=analysis_request,
            output_root=Path(output_root),
            txt_max_rows_per_file=settings.txt_max_rows,
            generate_txt=settings.generate_txt,
            generate_excel_report=settings.generate_excel_report,
        )

    @staticmethod
    def validate_settings(settings: AttDataRepairSettings) -> None:
        """Raise when typed settings are not runnable."""

        if settings.minimum_duration_minutes < 1 or settings.minimum_duration_minutes > 1440:
            raise ValueError("Minimum_Duration_Minutes harus 1 sampai 1440.")
        if settings.txt_max_rows < 1:
            raise ValueError("TXT_Max_Rows harus lebih besar dari nol.")
        for field_name in (
            "saturday_missing_out_default",
            "midnight_time_out_default",
        ):
            if not isinstance(getattr(settings, field_name), time):
                raise ValueError(f"{field_name} harus datetime.time.")
        for label, start, end in (
            ("Weekday", settings.weekday_default_in, settings.weekday_default_out),
            ("Saturday", settings.saturday_default_in, settings.saturday_default_out),
            (
                "Sunday",
                settings.sunday_invalid_default_in,
                settings.sunday_invalid_default_out,
            ),
        ):
            if end <= start:
                raise ValueError(f"{label} default out harus lebih besar dari in.")
        if not settings.generate_txt and not settings.generate_excel_report:
            raise ValueError(
                "Minimal salah satu dari Generate_TXT atau "
                "Generate_Excel_Report harus TRUE."
            )


def _parse_time(value: object) -> time:
    text = str(value).strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        return time(int(hour_text), int(minute_text))
    except Exception as exc:
        raise ValueError(f"Format waktu konfigurasi invalid: {value!r}") from exc
