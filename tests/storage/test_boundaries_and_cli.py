"""DB3 scope boundaries and safe manual CLI behavior."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory
from shared.storage import get_database_path
from shared.storage.exceptions import RegistryAccessError
from shared.storage.registry import windows_registry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI = (
    PROJECT_ROOT
    / "tools"
    / "storage_test"
    / "storage_bootstrap_cli.py"
)


def test_storage_import_does_not_import_engine_or_gui(
    tmp_path: Path,
) -> None:
    script = (
        "import sys; import shared.storage; "
        "bad=[name for name in sys.modules if "
        "name.endswith('.engine') or name.endswith('.gui')]; "
        "print('|'.join(sorted(bad)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == ""
    assert not tuple(tmp_path.iterdir())


def test_windows_backend_reports_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(windows_registry, "winreg", None)

    with pytest.raises(RegistryAccessError):
        windows_registry.WindowsRegistryBackend()


def test_cli_requires_explicit_data_root() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), "--show-layout"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--data-root" in result.stderr


def test_cli_show_layout_does_not_create_root(tmp_path: Path) -> None:
    root = tmp_path / "manual"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--data-root",
            str(root),
            "--show-layout",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert '"database_path"' in result.stdout
    assert not root.exists()


def test_cli_initialize_uses_explicit_temp_without_registry(
    tmp_path: Path,
) -> None:
    root = tmp_path / "manual"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--data-root",
            str(root),
            "--initialize",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert '"success": true' in result.stdout
    assert get_database_path(root).is_file()
    assert '"registry_updated": false' in result.stdout


def test_bootstrap_schema_remains_exactly_24_tables(
    bootstrapped_root: Path,
) -> None:
    with SQLiteConnectionFactory().connect(
        get_database_path(bootstrapped_root),
        read_only=True,
    ) as connection:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchone()[0]

    assert count == 24


def test_restore_reset_and_full_import_are_not_exposed() -> None:
    import shared.storage as storage

    assert not hasattr(storage, "restore_from_backup")
    assert not hasattr(storage, "reset_to_default")
    assert not hasattr(storage, "import_existing_database")
