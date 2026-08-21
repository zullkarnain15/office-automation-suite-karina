"""JSON manifest serialization for standard application-data ZIP backups."""

from __future__ import annotations

import json
from dataclasses import asdict

from shared.recovery.models import BackupManifest


def manifest_to_json(manifest: BackupManifest) -> str:
    return json.dumps(asdict(manifest), indent=2, sort_keys=True)


def manifest_from_json(value: str) -> BackupManifest:
    data = json.loads(value)
    required = {
        "format_version",
        "application_version",
        "schema_version",
        "created_at",
        "source_data_root",
        "database_relative_path",
        "database_sha256",
        "included_paths",
        "excluded_paths",
        "recorder_profile_count",
    }
    missing = required.difference(data)
    if missing:
        raise ValueError("Manifest fields missing: " + ", ".join(sorted(missing)))
    return BackupManifest(
        format_version=int(data["format_version"]),
        application_version=str(data["application_version"]),
        schema_version=int(data["schema_version"]),
        created_at=str(data["created_at"]),
        source_data_root=str(data["source_data_root"]),
        database_relative_path=str(data["database_relative_path"]),
        database_sha256=str(data["database_sha256"]),
        included_paths=tuple(str(item) for item in data["included_paths"]),
        excluded_paths=tuple(str(item) for item in data["excluded_paths"]),
        recorder_profile_count=int(data["recorder_profile_count"]),
    )
