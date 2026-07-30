"""Atomic transaction state storage for application updates."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from shared.database.time_utils import current_timestamp
from shared.storage.path_resolver import resolve_storage_layout
from shared.update.exceptions import UpdateTransactionError
from shared.update.models import (
    TRANSACTION_STATUSES,
    UpdateTransaction,
)
from shared.update.path_safety import require_under, resolved

TRANSACTIONS_DIRECTORY = "transactions"
TRANSACTION_FILENAME = "transaction.json"


class UpdateTransactionStore:
    def __init__(self, data_root: str | Path) -> None:
        self.data_root = resolved(data_root)
        self.update_root = self.data_root / "update"
        self.transactions_root = self.update_root / TRANSACTIONS_DIRECTORY

    def create(
        self,
        *,
        current_version: str,
        target_version: str,
        package_path: Path,
        package_sha256: str,
        staging_path: Path,
        application_root: Path,
        database_backup_path: Path,
        entry_executable: str,
        source_process_id: int | None = None,
    ) -> UpdateTransaction:
        transaction_id = str(uuid.uuid4())
        transaction_dir = self.transactions_root / transaction_id
        rollback_path = self.update_root / "rollback" / transaction_id
        log_path = self.update_root / "logs" / f"update_{transaction_id}.log"
        timestamp = current_timestamp()
        transaction = UpdateTransaction(
            transaction_id=transaction_id,
            status="STAGED",
            current_version=current_version,
            target_version=target_version,
            package_path=resolved(package_path),
            package_sha256=package_sha256,
            staging_path=resolved(staging_path),
            staged_application_path=resolved(staging_path) / "application",
            application_root=resolved(application_root),
            rollback_path=rollback_path,
            database_backup_path=resolved(database_backup_path),
            entry_executable=entry_executable,
            source_process_id=source_process_id,
            new_process_id=None,
            created_at=timestamp,
            updated_at=timestamp,
            last_error=None,
            log_path=log_path,
            transaction_path=transaction_dir / TRANSACTION_FILENAME,
        )
        self.validate_paths(transaction)
        self.save(transaction)
        return transaction

    def load(self, transaction_path: str | Path) -> UpdateTransaction:
        path = self._validate_transaction_path(transaction_path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise UpdateTransactionError(f"Transaction tidak dapat dibaca: {exc}") from exc
        if not isinstance(raw, dict):
            raise UpdateTransactionError("Transaction JSON harus berupa object.")
        transaction = self._from_json(raw, path)
        self.validate_paths(transaction)
        return transaction

    def save(self, transaction: UpdateTransaction) -> None:
        if transaction.status not in TRANSACTION_STATUSES:
            raise UpdateTransactionError(f"Status transaksi tidak didukung: {transaction.status}")
        path = transaction.transaction_path
        if path is None:
            raise UpdateTransactionError("Transaction path kosong.")
        path = self._validate_transaction_path(path, allow_missing=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._to_json(transaction)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file_handle:
                json.dump(payload, file_handle, indent=2, sort_keys=True)
                file_handle.write("\n")
                file_handle.flush()
                os.fsync(file_handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def update_status(
        self,
        transaction: UpdateTransaction,
        status: str,
        *,
        last_error: str | None = None,
        new_process_id: int | None = None,
    ) -> UpdateTransaction:
        updated = replace(
            transaction,
            status=status,
            updated_at=current_timestamp(),
            last_error=last_error,
            new_process_id=(
                transaction.new_process_id if new_process_id is None else new_process_id
            ),
        )
        self.save(updated)
        return updated

    def latest_non_terminal(self) -> UpdateTransaction | None:
        if not self.transactions_root.exists():
            return None
        candidates: list[UpdateTransaction] = []
        for path in self.transactions_root.glob(f"*/{TRANSACTION_FILENAME}"):
            try:
                transaction = self.load(path)
            except UpdateTransactionError:
                continue
            if not transaction.is_terminal:
                candidates.append(transaction)
        return max(candidates, key=lambda item: item.updated_at, default=None)

    def validate_paths(self, transaction: UpdateTransaction) -> None:
        layout = resolve_storage_layout(self.data_root)
        require_under(transaction.transaction_path or "", self.transactions_root, "Transaction path di luar update/transactions.")
        require_under(transaction.staging_path, self.update_root / "staging", "Staging path di luar Data Root/update/staging.")
        require_under(transaction.staged_application_path, transaction.staging_path, "Staged application path di luar staging.")
        require_under(transaction.rollback_path, layout.data_root / "update" / "rollback", "Rollback path di luar Data Root/update/rollback.")
        if transaction.application_root == layout.data_root:
            raise UpdateTransactionError("Application Root tidak boleh sama dengan Data Root.")
        if transaction.application_root in layout.data_root.parents:
            raise UpdateTransactionError("Application Root tidak boleh berada di bawah Data Root.")
        if transaction.rollback_path in transaction.application_root.parents:
            raise UpdateTransactionError("Rollback path tidak boleh berada di Application Root.")

    def _validate_transaction_path(
        self,
        transaction_path: str | Path,
        *,
        allow_missing: bool = False,
    ) -> Path:
        path = require_under(
            transaction_path,
            self.transactions_root,
            "Transaction path arbitrary ditolak.",
        )
        if path.name != TRANSACTION_FILENAME:
            raise UpdateTransactionError("Nama transaction file tidak valid.")
        if path.parent.parent != self.transactions_root:
            raise UpdateTransactionError("Transaction harus berada di update/transactions/<id>.")
        if not allow_missing and not path.is_file():
            raise UpdateTransactionError(f"Transaction tidak ditemukan: {path}")
        return path

    @staticmethod
    def _to_json(transaction: UpdateTransaction) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in fields(UpdateTransaction):
            if field.name == "transaction_path":
                continue
            value = getattr(transaction, field.name)
            if isinstance(value, Path):
                payload[field.name] = str(value)
            else:
                payload[field.name] = value
        return payload

    @staticmethod
    def _from_json(raw: dict[str, Any], path: Path) -> UpdateTransaction:
        required = {field.name for field in fields(UpdateTransaction)} - {"transaction_path"}
        missing = sorted(required - set(raw))
        if missing:
            raise UpdateTransactionError("Transaction kehilangan field: " + ", ".join(missing))
        path_fields = {
            "package_path",
            "staging_path",
            "staged_application_path",
            "application_root",
            "rollback_path",
            "database_backup_path",
            "log_path",
        }
        values = dict(raw)
        for name in path_fields:
            if values.get(name) is not None:
                values[name] = Path(values[name])
        values["transaction_path"] = path
        return UpdateTransaction(**values)
