"""In-memory Registry backend for deterministic isolated tests."""

from __future__ import annotations

from shared.storage.exceptions import RegistryAccessError


class FakeRegistryBackend:
    def __init__(
        self,
        *,
        available: bool = True,
        initial: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.available = available
        self.values = {
            key: dict(items) for key, items in (initial or {}).items()
        }
        self.read_count = 0
        self.write_count = 0
        self.delete_count = 0

    def _ensure_available(self) -> None:
        if not self.available:
            raise RegistryAccessError("Registry backend is unavailable.")

    def read_value(self, key: str, name: str) -> str | None:
        self._ensure_available()
        self.read_count += 1
        return self.values.get(key, {}).get(name)

    def write_values(self, key: str, values: dict[str, str]) -> None:
        self._ensure_available()
        self.write_count += 1
        self.values.setdefault(key, {}).update(values)

    def delete_key(self, key: str) -> None:
        self._ensure_available()
        self.delete_count += 1
        self.values.pop(key, None)

    def key_exists(self, key: str) -> bool:
        self._ensure_available()
        return key in self.values
