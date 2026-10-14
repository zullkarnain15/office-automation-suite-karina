"""SQLite backup API and DB1 scope-isolation tests."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from shared.database import (
    SCHEMA_VERSION,
    BackupError,
    BackupManager,
    DatabaseValidator,
    REQUIRED_TABLES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_sqlite_backup_is_valid_and_source_is_unchanged(
    database_path: Path,
    tmp_path: Path,
) -> None:
    source_hash_before = _sha256(database_path)
    backup_path = tmp_path / "backup" / "OAS-K-test-backup.db"

    result = BackupManager().create_backup(
        database_path,
        backup_path,
        create_parent=True,
    )

    assert backup_path.is_file()
    assert result.validation.is_valid is True
    assert result.schema_version == SCHEMA_VERSION
    assert result.sha256 == _sha256(backup_path)
    assert _sha256(database_path) == source_hash_before
    assert DatabaseValidator().validate(backup_path).is_valid is True


def test_backup_does_not_overwrite_without_permission(
    database_path: Path,
    tmp_path: Path,
) -> None:
    backup_path = tmp_path / "existing.db"
    backup_path.write_bytes(b"keep me")

    with pytest.raises(BackupError, match="already exists"):
        BackupManager().create_backup(database_path, backup_path)
    assert backup_path.read_bytes() == b"keep me"


def test_backup_filename_is_safe() -> None:
    filename = BackupManager.suggested_filename()

    assert filename.startswith("OAS-K_")
    assert filename.endswith(".db")
    assert ":" not in filename


def test_manual_database_tool_uses_explicit_temp_paths(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "manual-test.db"
    backup_path = tmp_path / "manual-backup.db"
    completed = subprocess.run(
        [
            sys.executable,
            str(
                PROJECT_ROOT
                / "tools"
                / "database_test"
                / "create_test_database.py"
            ),
            "--output",
            str(database_path),
            "--backup",
            str(backup_path),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert database_path.is_file()
    assert backup_path.is_file()
    assert f"Schema version: {SCHEMA_VERSION}" in completed.stdout
    assert f"Table count: {len(REQUIRED_TABLES)}" in completed.stdout
    assert "Validation: PASS" in completed.stdout


def test_database_package_does_not_import_engines_or_gui() -> None:
    code = """
import json
import sys
import shared.database

prefixes = ("attendance", "outlook", "hris", "utilities", "tkinter")
loaded = sorted(
    name for name in sys.modules
    if name in prefixes
    or name.startswith(tuple(item + "." for item in prefixes))
)
print(json.dumps(loaded))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "[]"


def test_database_package_has_no_registry_usage() -> None:
    database_root = PROJECT_ROOT / "shared" / "database"
    python_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in database_root.rglob("*.py")
    )

    assert "winreg" not in python_sources
    assert "HKEY_" not in python_sources


def test_tests_do_not_create_database_in_project_root() -> None:
    root_databases = [
        *PROJECT_ROOT.glob("*.db"),
        *PROJECT_ROOT.glob("*.sqlite"),
        *PROJECT_ROOT.glob("*.sqlite3"),
    ]

    assert root_databases == []
