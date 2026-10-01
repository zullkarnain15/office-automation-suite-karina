"""Rollback helpers for restoring the previous OAS-K application."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from updater.application_replacer import ApplicationReplacementError, resolved


def restore_previous_application(
    *,
    application_root: Path,
    rollback_path: Path,
    data_root: Path,
    entry_executable: str,
) -> Path:
    app = resolved(application_root)
    rollback_application = resolved(rollback_path) / "application"
    data = resolved(data_root)
    if not rollback_application.is_dir():
        raise ApplicationReplacementError("Rollback application backup missing.")
    if not (rollback_application / entry_executable).is_file():
        raise ApplicationReplacementError("Rollback executable missing.")
    if app == data:
        raise ApplicationReplacementError("Application Root equals Data Root.")
    failed = data / "update" / "failed" / rollback_path.name / "application"
    if app.exists():
        failed.parent.mkdir(parents=True, exist_ok=True)
        if failed.exists():
            shutil.rmtree(failed)
        os.replace(app, failed)
    temp_restore = app.with_name(f"{app.name}.restore")
    if temp_restore.exists():
        shutil.rmtree(temp_restore)
    shutil.copytree(rollback_application, temp_restore, symlinks=False)
    os.replace(temp_restore, app)
    if not (app / entry_executable).is_file():
        raise ApplicationReplacementError("Restored executable missing.")
    return app
