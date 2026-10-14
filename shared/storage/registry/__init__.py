"""Registry services with an injectable fake backend."""

from shared.storage.registry.fake_registry import FakeRegistryBackend
from shared.storage.registry.windows_registry import (
    StorageRegistryService,
    WindowsRegistryBackend,
)

__all__ = [
    "FakeRegistryBackend",
    "StorageRegistryService",
    "WindowsRegistryBackend",
]
