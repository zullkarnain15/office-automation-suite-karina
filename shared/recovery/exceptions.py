"""Domain exceptions for recovery operations."""


class RecoveryError(RuntimeError):
    """Base class for an explicit recovery operation failure."""


class CandidateValidationError(RecoveryError):
    """Raised when a database candidate is unsafe to activate."""


class ApplicationDataBackupError(RecoveryError):
    """Raised for invalid or unsafe application-data archives."""


class ConfirmationRequiredError(RecoveryError):
    """Raised when a destructive operation lacks explicit confirmation."""


class ActivationError(RecoveryError):
    """Raised when staged activation or rollback cannot complete."""
