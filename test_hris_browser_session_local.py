"""
Temporary local test file for Sprint 6.12 HRIS Browser Session.

This test does not access real HRIS URL.
It creates a local mock HRIS login page and opens it with Microsoft Edge.

Run from project root:
py test_hris_browser_session_local.py
"""

from __future__ import annotations

from pathlib import Path

from hris.browser import HRISBrowserManager
from shared.config_manager import HRISConfigurationReader


CONFIG_FILE = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\config\hris\OAS-K_HRIS_Configuration.xlsx"
)

MOCK_SITE_FOLDER = Path(
    r"D:\Python Project\OfficeAutomationSuite-Karina\temp\hris_mock_site"
)

MOCK_LOGIN_FILE = MOCK_SITE_FOLDER / "login.html"


def create_mock_hris_login_page() -> None:
    """
    Create local mock HRIS login page for browser test.
    """
    MOCK_SITE_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mock HRIS Login - OAS-K</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f5f5f5;
            padding: 40px;
        }

        .card {
            width: 420px;
            margin: auto;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        h1 {
            color: #1F4E78;
            font-size: 22px;
            margin-bottom: 8px;
        }

        p {
            color: #555;
        }

        label {
            display: block;
            margin-top: 14px;
            font-weight: bold;
        }

        input {
            width: 100%;
            padding: 8px;
            margin-top: 6px;
            box-sizing: border-box;
        }

        button {
            margin-top: 18px;
            width: 100%;
            padding: 10px;
            background: #2E8B57;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            cursor: pointer;
        }

        .success {
            margin-top: 18px;
            color: #2E8B57;
            font-weight: bold;
            display: none;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Mock HRIS Login</h1>
        <p>This is a local mock page for OAS-K browser testing.</p>

        <label>User ID</label>
        <input id="username" type="text" value="test.user">

        <label>Password</label>
        <input id="password" type="password" value="password">

        <button onclick="document.getElementById('success').style.display='block';">
            Login
        </button>

        <div id="success" class="success">
            Login simulated successfully. You can return to terminal and press ENTER.
        </div>
    </div>
</body>
</html>
"""

    MOCK_LOGIN_FILE.write_text(
        html,
        encoding="utf-8",
    )


def main() -> None:
    print("=" * 80)
    print("OAS-K Sprint 6.12 HRIS Browser Session Local Test")
    print("=" * 80)

    create_mock_hris_login_page()

    reader = HRISConfigurationReader(CONFIG_FILE)
    configuration = reader.read()

    local_url = MOCK_LOGIN_FILE.resolve().as_uri()

    configuration.general["HRIS_URL"] = local_url

    print()
    print("LOCAL MOCK HRIS URL")
    print("-" * 80)
    print(local_url)

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

        browser_manager.wait_for_manual_login(
            message=(
                "Local mock HRIS page sudah terbuka. "
                "Klik tombol Login di browser, lalu tekan ENTER di terminal ini..."
            )
        )

        print()
        print("MANUAL LOGIN CONFIRMATION")
        print("-" * 80)
        print("Operator confirmed mock login manually.")
        print(f"Current Page URL: {session.page.url}")

    finally:
        print()
        print("Closing browser session...")
        browser_manager.close()

    print()
    print("=" * 80)
    print("HRIS Browser Session local test finished.")
    print("=" * 80)


if __name__ == "__main__":
    main()