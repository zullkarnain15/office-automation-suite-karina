"""Per-job process log writer using concise, non-sensitive messages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.logger import get_logger

logger = get_logger(__name__)


class ReconciliationProcessLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        logger.info("Reconciliation: %s", message)
