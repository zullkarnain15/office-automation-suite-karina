"""
Temporary test file for Sprint 5.3 Raw Log Extractor.

Run from project root:
python test_raw_log_extractor.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from attendance.extractor import AttendanceMDBExtractor
from config.app_config import DATE_FORMAT


MDB_PATH = Path(
    r"D:\Python Project\Attendance Configuration\mdb\HO\newatt2000.mdb"
)

DATE_FROM = "03/30/2026"
DATE_TO = "03/30/2026"


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
    print("OAS-K Attendance Raw Log Extractor Test")
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

        print("RAW LOG RESULT")
        print("-" * 80)
        print(f"Total raw log(s): {len(raw_logs)}")
        print()

        print("SAMPLE RAW LOGS")
        print("-" * 80)

        for raw_log in raw_logs[:30]:
            print(raw_log)

        print()
        print("BASIC CHECK")
        print("-" * 80)

        unique_nik = {
            raw_log["nik"]
            for raw_log in raw_logs
            if raw_log["nik"]
        }

        print(f"Unique NIK count : {len(unique_nik)}")

        missing_nik = [
            raw_log
            for raw_log in raw_logs
            if not raw_log["nik"]
        ]

        print(f"Missing NIK logs : {len(missing_nik)}")

    print()
    print("=" * 80)
    print("Raw log extraction finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()