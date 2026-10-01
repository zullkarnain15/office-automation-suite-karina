"""Launch the standalone updater from Data Root runtime storage."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from shared.update.exceptions import UpdateApplyError, UpdateTransactionError
from shared.update.models import ApplyRequestResult, UpdateTransaction
from shared.update.path_safety import reject_overlap, require_under, resolved
from shared.update.transaction_store import UpdateTransactionStore
from shared.update.updater_resource import (
    UPDATER_EXECUTABLE_NAME,
    UpdaterResource,
    default_updater_resource,
    explicit_updater_resource,
)

RUNTIME_DIRECTORY = "runtime"
UPDATER_VERSION = "python-dev"


class UpdaterLauncher:
    def __init__(
        self,
        data_root: str | Path,
        *,
        updater_source: str | Path | None = None,
        python_executable: str | Path | None = None,
    ) -> None:
        self.data_root = resolved(data_root)
        self.update_root = self.data_root / "update"
        self.runtime_base_root = self.update_root / RUNTIME_DIRECTORY
        self.updater_resource = (
            explicit_updater_resource(updater_source)
            if updater_source is not None
            else default_updater_resource()
        )
        self.python_executable = Path(python_executable or sys.executable)
        self.store = UpdateTransactionStore(self.data_root)

    def ensure_runtime(
        self,
        application_root: str | Path,
        *,
        runtime_id: str | None = None,
    ) -> Path:
        source = self.updater_resource
        target_root = self.runtime_base_root / (runtime_id or UPDATER_VERSION)
        reject_overlap(application_root, target_root, "Updater runtime berada di Application Root.")
        target_root.mkdir(parents=True, exist_ok=True)
        target = _runtime_target(source, target_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        shutil.copy2(source.path, target)
        source_digest = _file_digest(source.path)
        target_digest = _file_digest(target)
        if source_digest != target_digest:
            raise UpdateApplyError("Checksum updater runtime tidak cocok setelah copy.")
        if not target.is_file():
            raise UpdateApplyError("Updater runtime tidak tersedia setelah copy.")
        return target

    def launch(
        self,
        transaction: UpdateTransaction,
        *,
        wait_pid: int | None = None,
        shutdown_timeout: int = 60,
        health_timeout: int = 90,
    ) -> ApplyRequestResult:
        if transaction.status != "STAGED":
            raise UpdateTransactionError("Hanya transaction STAGED yang dapat di-apply.")
        updater_main = self.ensure_runtime(
            transaction.application_root,
            runtime_id=transaction.transaction_id,
        )
        require_under(
            transaction.transaction_path or "",
            self.update_root / "transactions",
            "Transaction path di luar update/transactions.",
        )
        updated = self.store.update_status(
            transaction,
            "APPLY_REQUESTED",
            new_process_id=None,
        )
        arguments = (
            "--transaction",
            str(updated.transaction_path),
            "--wait-pid",
            str(wait_pid or os.getpid()),
            "--shutdown-timeout",
            str(shutdown_timeout),
            "--health-timeout",
            str(health_timeout),
            "--log-path",
            str(updated.log_path),
        )
        if updater_main.name.casefold() == UPDATER_EXECUTABLE_NAME.casefold():
            command = (str(updater_main), *arguments)
        else:
            command = (
                str(self.python_executable),
                str(updater_main),
                *arguments,
                "--python-executable",
                str(self.python_executable),
            )
        process = subprocess.Popen(command, cwd=updater_main.parent)
        return ApplyRequestResult(
            transaction=updated,
            updater_path=updater_main,
            process_id=process.pid,
            command=command,
        )


def _runtime_target(source: UpdaterResource, target_root: Path) -> Path:
    if source.is_executable:
        return target_root / UPDATER_EXECUTABLE_NAME
    return target_root / "updater" / "main.py"


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
