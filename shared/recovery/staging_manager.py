"""Unique Data Root staging directories and atomic database activation."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from shared.recovery.constants import RECOVERY_STAGING_DIRECTORY
from shared.storage.path_resolver import resolve_storage_layout


class StagingManager:
    def create(self, data_root: str | Path) -> tuple[str, Path]:
        operation_id = uuid.uuid4().hex
        diagnostics = resolve_storage_layout(data_root).diagnostics_root
        staging = diagnostics / RECOVERY_STAGING_DIRECTORY / operation_id
        staging.mkdir(parents=True, exist_ok=False)
        return operation_id, staging

    @staticmethod
    def activate(
        staged_database: Path,
        active_database: Path,
        rollback_database: Path,
    ) -> None:
        active_database.parent.mkdir(parents=True, exist_ok=True)
        rollback_database.unlink(missing_ok=True)
        if active_database.exists():
            os.replace(active_database, rollback_database)
        try:
            os.replace(staged_database, active_database)
        except Exception:
            if rollback_database.exists() and not active_database.exists():
                os.replace(rollback_database, active_database)
            raise

    @staticmethod
    def rollback(active_database: Path, rollback_database: Path) -> bool:
        if not rollback_database.exists():
            return False
        active_database.unlink(missing_ok=True)
        os.replace(rollback_database, active_database)
        return True

    @staticmethod
    def cleanup(staging: Path) -> None:
        shutil.rmtree(staging, ignore_errors=True)
