"""
Temporary test file for Sprint 6.7 HRIS Configuration Reader.

Run from project root:
python test_hris_configuration_reader.py
"""

from __future__ import annotations

from pathlib import Path

from shared.config_manager import HRISConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\config\hris\OAS-K_HRIS_Configuration.xlsx"
)


def main() -> None:
    print("=" * 80)
    print("OAS-K HRIS Configuration Reader Test")
    print("=" * 80)
    print(f"Configuration File: {CONFIG_FILE}")
    print()

    reader = HRISConfigurationReader(CONFIG_FILE)
    config = reader.read()

    print("GENERAL CONFIG")
    print("-" * 80)
    for key, value in config.general.items():
        print(f"{key}: {value}")

    print()
    print("BROWSER CONFIG")
    print("-" * 80)
    for key, value in config.browser.items():
        print(f"{key}: {value}")

    print()
    print("UPLOAD CONFIG")
    print("-" * 80)
    for key, value in config.upload.items():
        print(f"{key}: {value}")

    print()
    print("HO RUN CONTROL LIST")
    print("-" * 80)
    if not config.ho_run_controls:
        print("(No active HO Run Control)")
    else:
        for item in config.ho_run_controls:
            print(
                f"Sequence={item.sequence} | "
                f"Workflow={item.workflow} | "
                f"Run_Control_ID={item.run_control_id} | "
                f"Description={item.description}"
            )

    print()
    print("BRANCH RUN CONTROL LIST")
    print("-" * 80)
    if not config.branch_run_controls:
        print("(No active Branch Run Control)")
    else:
        for item in config.branch_run_controls:
            print(
                f"Sequence={item.sequence} | "
                f"Workflow={item.workflow} | "
                f"Run_Control_ID={item.run_control_id} | "
                f"Description={item.description}"
            )

    print()
    print("BASIC CHECK")
    print("-" * 80)
    print(f"Active HO Run Control count     : {len(config.ho_run_controls)}")
    print(f"Active Branch Run Control count : {len(config.branch_run_controls)}")

    if config.ho_run_controls:
        first_ho = config.ho_run_controls[0]
        print(f"First HO Run Control ID         : {first_ho.run_control_id}")
        print(f"First HO Run Control ID type    : {type(first_ho.run_control_id).__name__}")

    print()
    print("=" * 80)
    print("HRIS configuration reader test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()
