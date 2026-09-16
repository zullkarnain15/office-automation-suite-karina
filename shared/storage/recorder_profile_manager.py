"""Safe relative references for external HRIS recorder JSON profiles."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from shared.storage.exceptions import RecorderProfileError
from shared.storage.models import (
    RecorderProfileReference,
    RecorderProfileValidationResult,
)
from shared.storage.path_resolver import get_recorder_profiles_root

logger = logging.getLogger(__name__)


def to_relative_profile_path(
    data_root: str | Path,
    profile_path: str | Path,
) -> Path:
    root = Path(data_root).expanduser().resolve()
    profiles_root = get_recorder_profiles_root(root).resolve()
    profile = Path(profile_path).expanduser().resolve()
    _require_json(profile)
    try:
        profile.relative_to(profiles_root)
        relative = profile.relative_to(root)
    except ValueError as exc:
        raise RecorderProfileError(
            "Recorder profile must be inside the recorder_profiles folder."
        ) from exc
    return relative


def resolve_profile_path(
    data_root: str | Path,
    relative_path: str | Path,
) -> Path:
    root = Path(data_root).expanduser().resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise RecorderProfileError(
            "Recorder profile reference must be a safe relative path."
        )
    if not relative.parts or relative.parts[0].casefold() != "recorder_profiles":
        raise RecorderProfileError(
            "Recorder profile reference must begin with recorder_profiles."
        )
    _require_json(relative)
    resolved = (root / relative).resolve()
    profiles_root = get_recorder_profiles_root(root).resolve()
    try:
        resolved.relative_to(profiles_root)
    except ValueError as exc:
        raise RecorderProfileError(
            "Recorder profile path escapes recorder_profiles."
        ) from exc
    return resolved


def validate_profile_reference(
    data_root: str | Path,
    relative_path: str | Path,
) -> RecorderProfileValidationResult:
    """Validate only storage-level JSON; do not inspect HRIS business steps."""

    warnings: list[str] = []
    errors: list[str] = []
    try:
        absolute = resolve_profile_path(data_root, relative_path)
        reference = RecorderProfileReference(
            relative_path=Path(relative_path),
            absolute_path=absolute,
        )
    except RecorderProfileError as exc:
        return RecorderProfileValidationResult(
            reference=None,
            exists=False,
            readable=False,
            json_object_valid=False,
            errors=(str(exc),),
        )

    if not absolute.exists():
        warnings.append(
            "Recorder profile file does not exist yet."
        )
        return RecorderProfileValidationResult(
            reference=reference,
            exists=False,
            readable=False,
            json_object_valid=False,
            warnings=tuple(warnings),
        )
    if not absolute.is_file():
        errors.append("Recorder profile reference is not a file.")
        readable = False
        valid_object = False
    else:
        try:
            with absolute.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
            readable = True
            valid_object = isinstance(payload, dict)
            if not valid_object:
                errors.append("Recorder profile JSON root must be an object.")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            readable = not isinstance(exc, OSError)
            valid_object = False
            errors.append(f"Recorder profile JSON is invalid: {exc}")
    logger.info(
        "Recorder profile validation: path=%s valid=%s",
        relative_path,
        not errors,
    )
    return RecorderProfileValidationResult(
        reference=reference,
        exists=True,
        readable=readable,
        json_object_valid=valid_object,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _require_json(path: Path) -> None:
    if path.suffix.casefold() != ".json":
        raise RecorderProfileError(
            "Recorder profile must use the .json extension."
        )
