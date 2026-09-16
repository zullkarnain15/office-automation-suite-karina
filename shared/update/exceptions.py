"""Exceptions for manual application update package preparation."""

from __future__ import annotations


class UpdateError(Exception):
    """Base class for update package failures."""


class UpdateValidationError(UpdateError):
    """Raised when an update package fails validation."""


class UpdateStagingError(UpdateError):
    """Raised when a package cannot be staged safely."""


class UpdateBackupError(UpdateError):
    """Raised when the required pre-update database backup fails."""


class UpdateBusyError(UpdateError):
    """Raised when another OAS-K job blocks update preparation."""


class UpdateTransactionError(UpdateError):
    """Raised when transaction state is invalid or unsafe."""


class UpdateApplyError(UpdateError):
    """Raised when an update cannot be requested for application."""


class UpdateHealthCheckError(UpdateError):
    """Raised when post-update health validation fails."""
