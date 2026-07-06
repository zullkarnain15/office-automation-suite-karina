"""
Temporary test file for Sprint 6.12 HRIS Browser Session.

Run from project root:
py test_hris_browser_session.py
"""

from __future__ import annotations

from pathlib import Path

from hris.browser import HRISBrowserManager
from shared.config_manager import HRISConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\config\hris\OAS-K_HRIS_Configuration.xlsx"
)


def main() -> None:
    print("=" * 80)
    print("OAS-K Sprint 6.12 HRIS Browser Session Test")
    print("=" * 80)

    reader = HRISConfigurationReader(CONFIG_FILE)
    configuration = reader.read()

    browser_manager = HRISBrowserManager(
        configuration=configuration,
    )

    session = None

    try:
        session = browser_manager.open_login_page()

        print()
        print("BROWSER SESSION")
        print("-" * 80)
        print(f"Page URL opened : {session.page.url}")
        print("Browser opened  : True")

        browser_manager.wait_for_manual_login()

        print()
        print("MANUAL LOGIN CONFIRMATION")
        print("-" * 80)
        print("Operator confirmed login manually.")
        print(f"Current Page URL: {session.page.url}")

    finally:
        print()
        print("Closing browser session...")
        browser_manager.close()

    print()
    print("=" * 80)
    print("HRIS Browser Session test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()