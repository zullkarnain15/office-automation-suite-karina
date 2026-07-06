"""
Temporary test file for Sprint 5.8 Attendance Configuration Reader.

Run from project root:
python test_attendance_configuration_reader.py
"""

from __future__ import annotations

from pathlib import Path

from shared.config_manager import AttendanceConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\Attendance Configuration\config\OAS-K_Attendance_Configuration.xlsx"
)


def main() -> None:
    print("=" * 80)
    print("OAS-K Attendance Configuration Reader Test")
    print("=" * 80)
    print(f"Configuration File: {CONFIG_FILE}")
    print()

    reader = AttendanceConfigurationReader(CONFIG_FILE)
    config = reader.read()

    print("GENERAL CONFIG")
    print("-" * 80)

    for key, value in config.general.items():
        print(f"{key}: {value}")

    print()
    print("OUTPUT CONFIG")
    print("-" * 80)

    for key, value in config.output.items():
        print(f"{key}: {value}")

    print()
    print("HO MDB LIST")
    print("-" * 80)

    if not config.ho_mdb_list:
        print("(No active HO MDB)")
    else:
        for index, item in enumerate(config.ho_mdb_list, start=1):
            print(
                f"{index}. "
                f"Code={item.code} | "
                f"Description={item.description} | "
                f"Path={item.mdb_path}"
            )

    print()
    print("BRANCH MDB LIST")
    print("-" * 80)

    if not config.branch_mdb_list:
        print("(No active Branch MDB)")
    else:
        for index, item in enumerate(config.branch_mdb_list, start=1):
            print(
                f"{index}. "
                f"Code={item.code} | "
                f"Description={item.description} | "
                f"Path={item.mdb_path}"
            )

    print()
    print("BASIC CHECK")
    print("-" * 80)
    print(f"Active HO MDB count     : {len(config.ho_mdb_list)}")
    print(f"Active Branch MDB count : {len(config.branch_mdb_list)}")

    print()
    print("=" * 80)
    print("Configuration reader test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()