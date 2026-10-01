"""Build helper for the standalone OAS-K updater.

This script only runs PyInstaller when explicitly executed by a user.
Codex must not run it unless an EXE build is explicitly requested.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPDATER_ENTRY = PROJECT_ROOT / "updater" / "main.py"
DIST_PATH = PROJECT_ROOT / "dist" / "updater"
WORK_PATH = PROJECT_ROOT / "build" / "updater"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build OAS-K-Updater.exe.")
    parser.add_argument(
        "--onefile",
        action="store_true",
        default=True,
        help="Build a small onefile updater executable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the PyInstaller command without running it.",
    )
    args = parser.parse_args(argv)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "OAS-K-Updater",
        "--distpath",
        str(DIST_PATH),
        "--workpath",
        str(WORK_PATH),
        "--specpath",
        str(WORK_PATH),
        "--console",
    ]
    if args.onefile:
        command.append("--onefile")
    command.append(str(UPDATER_ENTRY))
    print(" ".join(f'"{item}"' if " " in item else item for item in command))
    if args.dry_run:
        return 0
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
