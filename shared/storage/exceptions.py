"""Storage-layer domain exceptions."""


class StorageError(Exception):
    """Base class for OAS-K storage errors."""


class StorageValidationError(StorageError):
    """Raised when a data-root candidate is unsafe or unusable."""


class StorageBootstrapError(StorageError):
    """Raised when explicit storage initialization cannot complete."""


class RegistryAccessError(StorageError):
    """Raised when the Registry backend is unavailable or rejects access."""


class RegistryPointerMalformedError(RegistryAccessError):
    """Raised when persisted storage pointer values are incomplete or unsafe."""


class DataLocationChangeError(StorageError):
    """Raised when controlled data relocation cannot complete."""


class RecorderProfileError(StorageError):
    """Raised for unsafe recorder-profile references."""
