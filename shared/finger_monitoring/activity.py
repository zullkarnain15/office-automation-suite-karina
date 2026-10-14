"""Small in-process gate preventing maintenance from overlapping module work."""

from __future__ import annotations

import threading
from contextlib import contextmanager


class FingerMonitoringActivityGate:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._activities: dict[str, int] = {}
        self._exclusive: str | None = None

    @contextmanager
    def activity(self, name: str):
        with self._lock:
            if self._exclusive is not None:
                raise RuntimeError(f"Maintenance {self._exclusive} sedang berjalan.")
            self._activities[name] = self._activities.get(name, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                remaining = self._activities.get(name, 1) - 1
                if remaining:
                    self._activities[name] = remaining
                else:
                    self._activities.pop(name, None)

    @contextmanager
    def exclusive(self, name: str):
        with self._lock:
            if self._exclusive is not None or self._activities:
                active = self._exclusive or ", ".join(sorted(self._activities))
                raise RuntimeError(f"Operasi tidak dapat dimulai; aktivitas aktif: {active}.")
            self._exclusive = name
        try:
            yield
        finally:
            with self._lock:
                self._exclusive = None

    def status(self) -> dict[str, object]:
        with self._lock:
            return {"activities": tuple(sorted(self._activities)), "exclusive": self._exclusive}
