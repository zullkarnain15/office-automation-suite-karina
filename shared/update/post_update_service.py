"""Startup update notification and recovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.update.models import UpdateTransaction
from shared.update.transaction_store import UpdateTransactionStore


@dataclass(frozen=True, slots=True)
class StartupUpdateRecovery:
    transaction: UpdateTransaction
    recommendation: str


class PostUpdateService:
    def __init__(self, data_root: str | Path) -> None:
        self.store = UpdateTransactionStore(data_root)

    def detect_interrupted_transaction(self) -> StartupUpdateRecovery | None:
        transaction = self.store.latest_non_terminal()
        if transaction is None:
            return None
        recommendation = (
            "Restore Previous Application"
            if transaction.status
            in {
                "APPLYING",
                "APPLICATION_REPLACED",
                "STARTING_NEW_APPLICATION",
                "HEALTHCHECK_PENDING",
                "ROLLBACK_REQUESTED",
                "ROLLBACK_IN_PROGRESS",
            }
            else "Resume Recovery"
        )
        return StartupUpdateRecovery(transaction, recommendation)
