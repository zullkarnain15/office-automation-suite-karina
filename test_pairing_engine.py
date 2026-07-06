"""
Temporary test file for Sprint 5.4 Attendance Pairing Engine.

Run from project root:
python test_pairing_engine.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from attendance.engine import AttendancePairingEngine
from attendance.extractor import AttendanceMDBExtractor
from config.app_config import DATE_FORMAT


MDB_PATH = Path(
    r"D:\Python Project\Attendance Configuration\mdb\HO\newatt2000.mdb"
)

DATE_FROM = "03/30/2026"
DATE_TO = "03/30/2026"


def format_datetime(value: datetime | None) -> str:
    """Format datetime for display."""
    if value is None:
        return ""

    return value.strftime("%m/%d/%Y %H:%M:%S")


def main() -> None:
    date_from = datetime.strptime(
        DATE_FROM,
        DATE_FORMAT,
    )

    date_to = datetime.strptime(
        DATE_TO,
        DATE_FORMAT,
    )

    print("=" * 80)
    print("OAS-K Attendance Pairing Engine Test")
    print("=" * 80)
    print(f"MDB Path  : {MDB_PATH}")
    print(f"Date From : {DATE_FROM}")
    print(f"Date To   : {DATE_TO}")
    print()

    with AttendanceMDBExtractor(MDB_PATH) as extractor:
        raw_logs = extractor.fetch_raw_logs(
            date_from=date_from,
            date_to=date_to,
        )

    pairing_engine = AttendancePairingEngine()

    paired_records = pairing_engine.pair_raw_logs(raw_logs)

    summary = pairing_engine.summarize_pairing(paired_records)

    print("PAIRING SUMMARY")
    print("-" * 80)
    print(f"Raw log count              : {len(raw_logs)}")
    print(f"Pair result count          : {summary['total_records']}")
    print(f"Paired records             : {summary['paired_records']}")
    print(f"Single tap records         : {summary['single_tap_records']}")
    print(f"Missing NIK records        : {summary['missing_nik_records']}")
    print(
        "Invalid CHECKTIME records  : "
        f"{summary['invalid_checktime_records']}"
    )

    print()
    print("SAMPLE PAIRING RESULT")
    print("-" * 80)

    for record in paired_records[:50]:
        print(
            {
                "nik": record["nik"],
                "name": record["name"],
                "attendance_date": record["attendance_date"],
                "check_in": format_datetime(record["check_in"]),
                "check_out": format_datetime(record["check_out"]),
                "tap_count": record["tap_count"],
                "pair_status": record["pair_status"],
                "remarks": record["remarks"],
                "source_mdb": record["source_mdb"],
            }
        )

    print()
    print("=" * 80)
    print("Pairing test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()