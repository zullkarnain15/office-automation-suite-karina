"""DB2 importer fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SchemaManager

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ATTENDANCE_WORKBOOK = (
    PROJECT_ROOT
    / "config"
    / "attendance"
    / "OAS-K_Attendance_Configuration.xlsx"
)
HRIS_WORKBOOK = (
    PROJECT_ROOT / "config" / "hris" / "OAS-K_HRIS_Configuration.xlsx"
)
OUTLOOK_WORKBOOK = (
    PROJECT_ROOT
    / "config"
    / "outlook"
    / "OAS-K_Outlook-Revisi_Configuration.xlsx"
)
OUTLOOK_DUPLICATE = (
    PROJECT_ROOT
    / "config"
    / "outlook"
    / "OAS-K_Outlook-Revisi_Configuration1.xlsx"
)


@pytest.fixture
def db2_database(tmp_path: Path) -> Path:
    path = tmp_path / "db2.db"
    SchemaManager().initialize_database(path, "db2-test")
    return path
