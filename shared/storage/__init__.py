"""Windows data-root foundation with explicit, testable side effects."""

from shared.storage.constants import (
    DEFAULT_DATA_ROOT,
    REGISTRY_KEY,
    suggested_fallback_data_root,
)
from shared.storage.data_location_manager import (
    DataLocationManager,
    change_data_location,
)
from shared.storage.data_root_manager import (
    DataRootManager,
    resolve_startup_storage,
)
from shared.storage.exceptions import (
    DataLocationChangeError,
    RecorderProfileError,
    RegistryAccessError,
    StorageBootstrapError,
    StorageError,
    StorageValidationError,
)
from shared.storage.models import (
    DataLocationChangeRequest,
    DataLocationChangeResult,
    RecorderProfileReference,
    RecorderProfileValidationResult,
    StartupStorageResolution,
    StartupStorageStatus,
    StorageBootstrapRequest,
    StorageBootstrapResult,
    StorageLayout,
    StoragePointer,
    StorageValidationResult,
)
from shared.storage.path_resolver import (
    get_backup_root,
    get_database_path,
    get_diagnostics_root,
    get_hris_recorder_profiles_root,
    get_logs_root,
    get_output_root,
    get_recorder_profiles_root,
    resolve_storage_layout,
)
from shared.storage.recorder_profile_manager import (
    resolve_profile_path,
    to_relative_profile_path,
    validate_profile_reference,
)
from shared.storage.storage_bootstrap import (
    StorageBootstrapService,
    initialize_data_root,
    initialize_storage,
)
from shared.storage.storage_validator import (
    validate_data_root,
    validate_existing_database_candidate,
)

__all__ = [
    "DEFAULT_DATA_ROOT",
    "REGISTRY_KEY",
    "DataLocationChangeError",
    "DataLocationChangeRequest",
    "DataLocationChangeResult",
    "DataLocationManager",
    "DataRootManager",
    "RecorderProfileError",
    "RecorderProfileReference",
    "RecorderProfileValidationResult",
    "RegistryAccessError",
    "StartupStorageResolution",
    "StartupStorageStatus",
    "StorageBootstrapError",
    "StorageBootstrapRequest",
    "StorageBootstrapResult",
    "StorageBootstrapService",
    "StorageError",
    "StorageLayout",
    "StoragePointer",
    "StorageValidationError",
    "StorageValidationResult",
    "change_data_location",
    "get_backup_root",
    "get_database_path",
    "get_diagnostics_root",
    "get_hris_recorder_profiles_root",
    "get_logs_root",
    "get_output_root",
    "get_recorder_profiles_root",
    "initialize_data_root",
    "initialize_storage",
    "resolve_profile_path",
    "resolve_startup_storage",
    "resolve_storage_layout",
    "suggested_fallback_data_root",
    "to_relative_profile_path",
    "validate_data_root",
    "validate_existing_database_candidate",
    "validate_profile_reference",
]
