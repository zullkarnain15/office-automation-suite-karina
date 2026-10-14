"""Registry backend protocol with no platform import side effects."""

from __future__ import annotations

from typing import Protocol


class RegistryBackend(Protocol):
    def read_value(self, key: str, name: str) -> str | None:
        """Return one string value or None when it is missing."""

    def write_values(self, key: str, values: dict[str, str]) -> None:
        """Write multiple string values under one key."""

    def delete_key(self, key: str) -> None:
        """Delete the storage key when it exists."""

    def key_exists(self, key: str) -> bool:
        """Return whether the key exists."""
