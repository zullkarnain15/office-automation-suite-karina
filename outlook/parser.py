"""
Outlook - Revisi attachment parsing and TXT output helpers.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


REQUIRED_HO_COLUMNS = (
    "NIK",
    "DATE IN",
    "TIME IN",
    "DATE OUT",
    "TIMEOUT",
)


@dataclass(slots=True)
class AttendanceRevisionRecord:
    """Normalized attendance revision row."""

    nik: str
    date_in: date
    time_in: str
    date_out: date
    time_out: str
    source_file: Path
    source_row: int

    def to_txt_row(self) -> list[str]:
        """Return HRIS-ready quoted TXT row values."""
        return [
            self.date_in.strftime("%m/%d/%Y"),
            self.nik,
            self.date_in.strftime("%m/%d/%Y"),
            self.time_in,
            self.date_out.strftime("%m/%d/%Y"),
            self.time_out,
        ]


@dataclass(slots=True)
class ParseResult:
    """Attachment parse result."""

    records: list[AttendanceRevisionRecord]
    errors: list[str]

    @property
    def valid(self) -> bool:
        return not self.errors


class OutlookAttachmentParser:
    """Parse Outlook - Revisi attachments into normalized rows."""

    def parse(
        self,
        path: str | Path,
        workflow: str,
    ) -> ParseResult:
        """Parse an attachment according to workflow."""
        attachment_path = Path(path)
        workflow_label = self._normalize_workflow(workflow)

        if workflow_label == "HO":
            return self.parse_ho_excel(attachment_path)

        if workflow_label == "Branch":
            return self.parse_branch_txt(attachment_path)

        return ParseResult([], [f"Unsupported workflow: {workflow}"])

    def parse_ho_excel(self, path: Path) -> ParseResult:
        """Parse HO Excel attachment."""
        errors: list[str] = []
        records: list[AttendanceRevisionRecord] = []

        try:
            workbook = load_workbook(path, data_only=True, read_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
        except Exception as error:
            return ParseResult([], [f"Failed to read Excel attachment: {error}"])

        try:
            if not rows:
                return ParseResult([], ["Excel attachment is empty."])

            header_index = self._find_header_index(rows, REQUIRED_HO_COLUMNS)
            headers = [
                self._normalize_header(value)
                for value in rows[header_index]
            ]
            column_map = {
                header: index
                for index, header in enumerate(headers)
                if header
            }

            for row_number, row in enumerate(rows[header_index + 1:], header_index + 2):
                if self._is_empty_ho_data_row(row, column_map):
                    continue

                record = self._record_from_values(
                    nik=self._value_at(row, column_map["NIK"]),
                    date_in=self._value_at(row, column_map["DATE IN"]),
                    time_in=self._value_at(row, column_map["TIME IN"]),
                    date_out=self._value_at(row, column_map["DATE OUT"]),
                    time_out=self._value_at(row, column_map["TIMEOUT"]),
                    source_file=path,
                    source_row=row_number,
                    errors=errors,
                )

                if record is not None:
                    records.append(record)
        finally:
            try:
                workbook.close()
            except Exception:
                pass

        return ParseResult(records, errors)

    @classmethod
    def _is_empty_ho_data_row(
        cls,
        row: tuple[Any, ...],
        column_map: dict[str, int],
    ) -> bool:
        """Ignore unused template rows whose formulas evaluate to 0/00:00."""
        if not row:
            return True

        values = [
            cls._value_at(row, column_map[column])
            for column in REQUIRED_HO_COLUMNS
        ]
        return all(cls._is_empty_template_value(value) for value in values)

    @staticmethod
    def _is_empty_template_value(value: Any) -> bool:
        if value is None or not str(value).strip():
            return True

        if isinstance(value, (int, float)) and value == 0:
            return True

        if (
            hasattr(value, "hour")
            and hasattr(value, "minute")
            and not isinstance(value, datetime)
            and value.hour == 0
            and value.minute == 0
            and getattr(value, "second", 0) == 0
        ):
            return True

        return False

    def parse_branch_txt(self, path: Path) -> ParseResult:
        """Parse Branch TXT attachment with six comma-separated columns."""
        errors: list[str] = []
        records: list[AttendanceRevisionRecord] = []

        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                delimiter = "\t" if "\t" in sample and "," not in sample else ","
                reader = csv.reader(handle, delimiter=delimiter)
                for row_number, row in enumerate(reader, 1):
                    if not row or not any(value.strip() for value in row):
                        continue

                    values = [value.strip().strip('"') for value in row]
                    if row_number == 1 and self._looks_like_header(values):
                        continue

                    if len(values) != 6:
                        errors.append(
                            f"{path.name} row {row_number}: expected 6 columns, "
                            f"got {len(values)}."
                        )
                        continue

                    record = self._record_from_values(
                        nik=values[1],
                        date_in=values[0],
                        time_in=values[3],
                        date_out=values[4],
                        time_out=values[5],
                        source_file=path,
                        source_row=row_number,
                        errors=errors,
                    )

                    if record is not None:
                        records.append(record)
        except Exception as error:
            return ParseResult([], [f"Failed to read TXT attachment: {error}"])

        return ParseResult(records, errors)

    def _record_from_values(
        self,
        nik: Any,
        date_in: Any,
        time_in: Any,
        date_out: Any,
        time_out: Any,
        source_file: Path,
        source_row: int,
        errors: list[str],
    ) -> AttendanceRevisionRecord | None:
        nik_text = self._to_text(nik)
        date_in_value = self._parse_date(date_in)
        date_out_value = self._parse_date(date_out)
        time_in_text = self._parse_time(time_in)
        time_out_text = self._parse_time(time_out)
        prefix = f"{source_file.name} row {source_row}"

        if not nik_text:
            errors.append(f"{prefix}: NIK is required.")
            return None

        if date_in_value is None:
            errors.append(f"{prefix}: DATE IN is invalid.")
            return None

        if date_out_value is None:
            errors.append(f"{prefix}: DATE OUT is invalid.")
            return None

        if time_in_text is None:
            errors.append(f"{prefix}: TIME IN is invalid.")
            return None

        if time_out_text is None:
            errors.append(f"{prefix}: TIMEOUT is invalid.")
            return None

        return AttendanceRevisionRecord(
            nik=nik_text,
            date_in=date_in_value,
            time_in=time_in_text,
            date_out=date_out_value,
            time_out=time_out_text,
            source_file=source_file,
            source_row=source_row,
        )

    @classmethod
    def _find_header_index(
        cls,
        rows: list[tuple[Any, ...]],
        required_headers: tuple[str, ...],
    ) -> int:
        required = {
            cls._normalize_header(header)
            for header in required_headers
        }

        for index, row in enumerate(rows):
            actual = {
                cls._normalize_header(value)
                for value in row
                if cls._to_text(value)
            }
            if required.issubset(actual):
                return index

        raise ValueError(
            "Missing required HO column(s): "
            + ", ".join(required_headers)
        )

    @staticmethod
    def _value_at(row: tuple[Any, ...], index: int) -> Any:
        if index >= len(row):
            return None
        return row[index]

    @staticmethod
    def _normalize_header(value: Any) -> str:
        return OutlookAttachmentParser._to_text(value).upper().replace("_", " ")

    @staticmethod
    def _to_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _looks_like_header(values: list[str]) -> bool:
        normalized = {value.strip().upper().replace("_", " ") for value in values}
        return bool({"NIK", "DATE IN", "TIME IN", "DATE OUT", "TIMEOUT"} & normalized)

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        value_text = OutlookAttachmentParser._to_text(value)

        if not value_text:
            return None

        for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value_text, fmt).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _parse_time(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.strftime("%H:%M")

        if hasattr(value, "hour") and hasattr(value, "minute"):
            return f"{value.hour:02d}:{value.minute:02d}"

        value_text = OutlookAttachmentParser._to_text(value)

        if not value_text:
            return None

        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value_text, fmt).strftime("%H:%M")
            except ValueError:
                continue

        return None

    @staticmethod
    def _normalize_workflow(value: str) -> str:
        value_text = str(value or "").strip().lower()
        if value_text == "ho":
            return "HO"
        if value_text == "branch":
            return "Branch"
        return ""


class OutlookTxtWriter:
    """Write normalized Outlook - Revisi rows into split TXT files."""

    def write(
        self,
        records: list[AttendanceRevisionRecord],
        output_folder: str | Path,
        workflow: str,
        max_lines: int,
        job_id: str,
        prefix: str = "Outlook_Revisi",
    ) -> list[Path]:
        """Write records into one or more TXT files."""
        if not records:
            return []

        output_path = Path(output_folder)
        output_path.mkdir(parents=True, exist_ok=True)
        workflow_label = OutlookAttachmentParser._normalize_workflow(workflow)
        safe_prefix = f"{prefix}_{workflow_label or workflow}"
        date_suffix = str(job_id).split("_", maxsplit=1)[0]
        limit = max(max_lines, 1)
        files: list[Path] = []

        for chunk_index, start in enumerate(range(0, len(records), limit), 1):
            chunk = records[start:start + limit]
            file_path = output_path / (
                f"{safe_prefix}_{chunk_index:03d}_{date_suffix}.txt"
            )

            with file_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(
                    handle,
                    quoting=csv.QUOTE_ALL,
                    lineterminator="\n",
                )
                for record in chunk:
                    writer.writerow(record.to_txt_row())

            files.append(file_path)

        return files
