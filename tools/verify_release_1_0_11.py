"""Isolated release-gate verification for OAS-K 1.0.11."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyInstaller.archive.readers import CArchiveReader
import psutil
import win32con
import win32gui
import win32process

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.database_validator import DatabaseValidator
from shared.database.schema_manager import SchemaManager
from shared.storage.path_resolver import resolve_storage_layout
from shared.update import ApplicationUpdateService
from shared.update.health_check import PostUpdateHealthCheck
from ui.constants import APP_TITLE


VERSION = "1.0.11"
PREVIOUS_VERSION = "1.0.10"
CORE_SCHEMA = 4


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def database_dump(path: Path) -> tuple[str, ...]:
    with SQLiteConnectionFactory().connect(path, read_only=True) as connection:
        return tuple(connection.iterdump())


def main() -> None:
    release = ROOT / "dist" / "release" / f"v{VERSION}"
    package = release / f"OAS-K_Update_v{VERSION}.zip"
    executable = release / "application" / "OAS-K.exe"
    updater_build = ROOT / "dist" / "updater" / "OAS-K-Updater.exe"
    old_executable = (
        ROOT / "dist" / "release" / f"v{PREVIOUS_VERSION}"
        / "application" / "OAS-K.exe"
    )

    expected_entries = {
        "application/",
        "application/OAS-K.exe",
        "checksums.sha256",
        "manifest.json",
        "release_notes.txt",
    }
    with zipfile.ZipFile(package) as archive:
        entries = set(archive.namelist())
        assert entries == expected_entries, entries
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == VERSION
        assert manifest["minimum_current_version"] == PREVIOUS_VERSION
        assert (
            manifest["database_schema_from"],
            manifest["database_schema_to"],
            manifest["migration_required"],
        ) == (CORE_SCHEMA, CORE_SCHEMA, False)
        assert hashlib.sha256(archive.read("application/OAS-K.exe")).hexdigest() == sha256(
            executable
        )
        prohibited_zip_entries = [
            name
            for name in entries
            if Path(name).suffix.casefold()
            in {".db", ".mdb", ".sqlite", ".sqlite3", ".log"}
            or any(
                part.casefold()
                in {"data", "data root", "logs", "output", "backup", "backups", "recorder_profiles"}
                for part in name.replace("\\", "/").split("/")
            )
        ]
        assert not prohibited_zip_entries, prohibited_zip_entries

    sidecar_hash = package.with_suffix(".zip.sha256").read_text(encoding="utf-8").split()[0]
    assert sidecar_hash == sha256(package)

    frozen = CArchiveReader(str(executable))
    pyz = frozen.open_embedded_archive("PYZ.pyz")
    frozen_modules = set(pyz.toc)
    for module in (
        "shared.attendance_ot.schema",
        "shared.attendance_ot.enrichment",
        "shared.attendance_ot.reporting",
        "ui.pages.attendance_ot_page",
    ):
        assert module in frozen_modules, module
    embedded_updater_name = next(
        name
        for name in frozen.toc
        if name.replace("\\", "/") == "updater/OAS-K-Updater.exe"
    )
    assert hashlib.sha256(frozen.extract(embedded_updater_name)).hexdigest() == sha256(
        updater_build
    )
    prohibited_frozen_entries = [
        name
        for name in frozen.toc
        if Path(name).suffix.casefold()
        in {".db", ".mdb", ".sqlite", ".sqlite3", ".log"}
        or any(
            part.casefold() in {"logs", "output", "backup", "backups", "recorder_profiles"}
            for part in name.replace("\\", "/").split("/")
        )
    ]
    assert not prohibited_frozen_entries, prohibited_frozen_entries

    temp_parent = ROOT / ".codex_tmp"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release_1_0_11_", dir=temp_parent) as temp_name:
        smoke_root = Path(temp_name)
        app_root = smoke_root / "application"
        app_root.mkdir()
        shutil.copy2(old_executable, app_root / "OAS-K.exe")

        layout = resolve_storage_layout(smoke_root / "DataRoot")
        SchemaManager().initialize_database(
            layout.database_path,
            PREVIOUS_VERSION,
            create_parent=True,
        )
        with SQLiteConnectionFactory().connect(layout.database_path) as connection:
            connection.execute(
                "INSERT INTO global_settings "
                "(global_settings_id, output_root, updated_at, updated_by) "
                "VALUES (1, ?, CURRENT_TIMESTAMP, ?)",
                (str(layout.output_root), "Production schema4 release fixture"),
            )
            connection.execute(
                "INSERT INTO outlook_settings "
                "(outlook_settings_id, mailbox_smtp, payroll_period, updated_at) "
                "VALUES (1, 'release.fixture@example.com', '09-2026', CURRENT_TIMESTAMP)"
            )
            connection.commit()
        baseline_dump = database_dump(layout.database_path)

        preserved_paths = (
            layout.data_root / "output" / "existing.txt",
            layout.data_root / "recorder_profiles" / "hris" / "existing.json",
        )
        for path in preserved_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("preserve production user data", encoding="utf-8")
        preserved_hashes = {str(path): sha256(path) for path in preserved_paths}

        update_service = ApplicationUpdateService()
        validation = update_service.validate_package(
            package,
            current_version=PREVIOUS_VERSION,
            active_schema_version=CORE_SCHEMA,
        )
        assert validation.valid, validation.errors
        prepared = update_service.prepare_update(
            package,
            current_version=PREVIOUS_VERSION,
            data_root=layout.data_root,
            application_root=app_root,
        )
        assert DatabaseValidator(expected_version=CORE_SCHEMA).validate(
            prepared.backup_path
        ).is_valid
        assert database_dump(prepared.backup_path) == baseline_dump
        assert database_dump(layout.database_path) == baseline_dump

        health = PostUpdateHealthCheck(application_version=VERSION).run(
            prepared.transaction_path,
            create_ui_shell=False,
        )
        assert health.status == "SUCCESS"
        assert health.database_schema_version == CORE_SCHEMA
        assert all(health.checks.values()), health.checks
        assert database_dump(layout.database_path) == baseline_dump
        assert all(sha256(Path(path)) == digest for path, digest in preserved_hashes.items())

        launched = subprocess.Popen(
            [
                str(executable),
                "--post-update",
                "--update-transaction",
                str(prepared.transaction_path),
            ],
            cwd=executable.parent,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 30
            windows: list[int] = []
            while time.monotonic() < deadline and not windows:
                parent = psutil.Process(launched.pid)
                own_pids = {parent.pid} | {
                    process.pid for process in parent.children(recursive=True)
                }

                def collect(hwnd: int, _unused: object) -> None:
                    if (
                        win32process.GetWindowThreadProcessId(hwnd)[1] in own_pids
                        and win32gui.GetClassName(hwnd) == "TkTopLevel"
                        and win32gui.GetWindowText(hwnd) == APP_TITLE
                    ):
                        windows.append(hwnd)

                win32gui.EnumWindows(collect, None)
                if not windows:
                    time.sleep(0.25)
            assert windows, "Frozen application did not create the OAS-K Tk shell"
            for hwnd in windows:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            launched.wait(timeout=20)
        finally:
            try:
                parent = psutil.Process(launched.pid)
                processes = parent.children(recursive=True) + [parent]
                for process in processes:
                    if process.is_running():
                        process.terminate()
            except psutil.NoSuchProcess:
                pass

    report = {
        "status": "PASS",
        "version": VERSION,
        "minimum_current_version": PREVIOUS_VERSION,
        "database_schema_from": CORE_SCHEMA,
        "database_schema_to": CORE_SCHEMA,
        "migration_required": False,
        "package_sha256": sha256(package),
        "executable_sha256": sha256(executable),
        "updater_sha256": sha256(updater_build),
        "package_entries": sorted(expected_entries),
        "package_contains_prohibited_data": False,
        "frozen_attendance_ot_modules_verified": True,
        "frozen_updater_verified": True,
        "pre_update_backup_valid": True,
        "core_database_preserved": True,
        "existing_output_and_profiles_preserved": True,
        "post_update_health_check": "SUCCESS",
        "frozen_ui_shell_observed": True,
    }
    (release / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
