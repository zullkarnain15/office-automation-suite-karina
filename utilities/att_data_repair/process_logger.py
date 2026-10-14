"""Per-job Process.log writer for Att Data Repair."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path


class AttDataRepairProcessLogger:
    """Append concise UTF-8 process messages."""

    def __init__(
        self,
        path: str | Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.clock = clock or datetime.now
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def info(self, message: str) -> None:
        """Write an INFO message."""

        self.write("INFO", message)

    def warning(self, message: str) -> None:
        """Write a WARNING message."""

        self.write("WARNING", message)

    def error(self, message: str) -> None:
        """Write an ERROR message."""

        self.write("ERROR", message)

    def write(self, level: str, message: str) -> None:
        """Append one timestamped log line."""

        timestamp = self.clock().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} | {level.upper()} | {message}"
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
