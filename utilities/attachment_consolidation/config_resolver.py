"""Resolve the standard Outlook configuration in source and frozen runs."""

from __future__ import annotations

import sys
from pathlib import Path

from config.app_config import CONFIG_PATH


CONFIG_FILE_NAME = "OAS-K_Outlook-Revisi_Configuration.xlsx"


def resolve_outlook_configuration(explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"Configuration file tidak ditemukan: {path}")
        return path

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(
            Path(sys.executable).resolve().parent
            / "config"
            / "outlook"
            / CONFIG_FILE_NAME
        )
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(
            bundle_root / "config" / "outlook" / CONFIG_FILE_NAME
        )
    else:
        candidates.append(CONFIG_PATH / "outlook" / CONFIG_FILE_NAME)
        candidates.extend(
            sorted(
                (CONFIG_PATH / "outlook").glob(
                    "OAS-K_Outlook-Revisi_Configuration*.xlsx"
                )
            )
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Outlook - Revisi Configuration tidak ditemukan. "
        f"File yang dibutuhkan: {CONFIG_FILE_NAME}"
    )
