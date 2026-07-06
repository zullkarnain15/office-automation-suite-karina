"""
Temporary test file for Sprint 5.1 MDB Inspector.

Run from project root:
python test_mdb_inspector.py
"""

from __future__ import annotations

from pathlib import Path

from attendance.extractor import AttendanceMDBExtractor


MDB_PATH = Path(
    r"D:\Python Project\Attendance Configuration\mdb\HO\newatt2000.mdb"
)


def main() -> None:
    print("=" * 80)
    print("OAS-K Attendance MDB Inspector")
    print("=" * 80)
    print(f"MDB Path: {MDB_PATH}")
    print()

    with AttendanceMDBExtractor(MDB_PATH) as extractor:
        tables = extractor.list_tables()

        print("TABLE LIST")
        print("-" * 80)

        for index, table_name in enumerate(tables, start=1):
            print(f"{index}. {table_name}")

        print()
        print("=" * 80)
        print("TABLE STRUCTURE + SAMPLE DATA")
        print("=" * 80)

        for table_name in tables:
            print()
            print("=" * 80)
            print(f"TABLE: {table_name}")
            print("=" * 80)

            columns = extractor.list_columns(table_name)

            print("COLUMNS:")
            print("-" * 80)

            for column in columns:
                print(
                    f"- {column['column_name']} "
                    f"({column['type_name']})"
                )

            print()
            print("SAMPLE DATA:")
            print("-" * 80)

            try:
                records = extractor.preview_table(
                    table_name,
                    limit=5,
                )

                if not records:
                    print("(No sample data)")
                else:
                    for record in records:
                        print(record)

            except Exception as exc:
                print(f"Could not preview table: {exc}")

    print()
    print("=" * 80)
    print("Inspection finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()