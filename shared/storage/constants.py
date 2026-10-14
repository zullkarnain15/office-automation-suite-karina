"""Central storage and Registry constants for OAS-K."""

from __future__ import annotations

from pathlib import Path

DEFAULT_DATA_ROOT = Path("D:/OAS-K/Data")
SUGGESTED_FALLBACK_PARTS = ("Documents", "OAS-K", "Data")

DATABASE_DIRECTORY = "database"
DATABASE_FILENAME = "OAS-K.db"
RECORDER_PROFILES_DIRECTORY = "recorder_profiles"
HRIS_RECORDER_DIRECTORY = "hris"
BACKUP_DIRECTORY = "backup"
OUTPUT_DIRECTORY = "output"
LOGS_DIRECTORY = "logs"
DIAGNOSTICS_DIRECTORY = "diagnostics"

STANDARD_DIRECTORIES = (
    DATABASE_DIRECTORY,
    f"{RECORDER_PROFILES_DIRECTORY}/{HRIS_RECORDER_DIRECTORY}",
    BACKUP_DIRECTORY,
    OUTPUT_DIRECTORY,
    LOGS_DIRECTORY,
    DIAGNOSTICS_DIRECTORY,
)

REGISTRY_KEY = r"Software\OTO Finance\OAS-K"
REGISTRY_DATA_ROOT_VALUE = "DataRoot"
REGISTRY_DATABASE_PATH_VALUE = "DatabasePath"


def suggested_fallback_data_root(user_profile: Path | None = None) -> Path:
    """Return a UI suggestion without creating or activating it."""

    base = user_profile or Path.home()
    return base.joinpath(*SUGGESTED_FALLBACK_PARTS)
