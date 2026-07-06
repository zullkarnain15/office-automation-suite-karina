"""
Temporary test file for Sprint 5.2 Attendance Database Mapping.

Run from project root:
python test_mdb_mapping.py
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from pathlib import Path

from attendance.extractor import AttendanceMDBExtractor


MDB_PATH = Path(
    r"D:\Python Project\Attendance Configuration\mdb\HO\newatt2000.mdb"
)

DATE_FROM = "03/30/2026"
DATE_TO = "03/30/2026"


def main() -> None:
    date_from = datetime.strptime(
        DATE_FROM,
        "%m/%d/%Y",
    )

    date_to = datetime.strptime(
        DATE_TO,
        "%m/%d/%Y",
    ) + timedelta(days=1)

    print("=" * 80)
    print("OAS-K Attendance Database Mapping Test")
    print("=" * 80)
    print(f"MDB Path  : {MDB_PATH}")
    print(f"Date From : {DATE_FROM}")
    print(f"Date To   : {DATE_TO}")
    print()

    with AttendanceMDBExtractor(MDB_PATH) as extractor:
        connection = extractor._require_connection()
        cursor = connection.cursor()

        query = """
            SELECT TOP 50
                c.USERID,
                u.Badgenumber,
                u.Name,
                c.CHECKTIME,
                c.CHECKTYPE,
                c.VERIFYCODE,
                c.SENSORID
            FROM
                CHECKINOUT AS c
            LEFT JOIN
                USERINFO AS u
            ON
                c.USERID = u.USERID
            WHERE
                c.CHECKTIME >= ?
                AND c.CHECKTIME < ?
            ORDER BY
                c.CHECKTIME ASC
        """

        cursor.execute(
            query,
            date_from,
            date_to,
        )

        rows = cursor.fetchall()

        print("JOIN RESULT")
        print("-" * 80)

        if not rows:
            print("No records found.")
        else:
            for row in rows:
                print(
                    {
                        "USERID": row.USERID,
                        "NIK": row.Badgenumber,
                        "Name": row.Name,
                        "CHECKTIME": row.CHECKTIME,
                        "CHECKTYPE": row.CHECKTYPE,
                        "VERIFYCODE": row.VERIFYCODE,
                        "SENSORID": row.SENSORID,
                    }
                )

        print()
        print(f"Total sample row(s): {len(rows)}")

    print()
    print("=" * 80)
    print("Mapping test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()