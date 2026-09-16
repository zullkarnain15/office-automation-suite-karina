"""Storage-only HRIS recorder profile management."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from shared.storage.path_resolver import resolve_storage_layout
from shared.storage.recorder_profile_manager import (
    to_relative_profile_path,
    validate_profile_reference,
)
from ui.services.protocols import RecorderProfileItem


class RecorderProfileUIService:
    def list_profiles(
        self,
        data_root: Path,
    ) -> tuple[RecorderProfileItem, ...]:
        layout = resolve_storage_layout(data_root)
        if not layout.hris_recorder_profiles_root.is_dir():
            return ()
        values = []
        for path in sorted(layout.hris_recorder_profiles_root.glob("*.json")):
            relative = to_relative_profile_path(data_root, path)
            validation = validate_profile_reference(data_root, relative)
            values.append(
                RecorderProfileItem(
                    path.name,
                    relative,
                    path.stat().st_mtime,
                    validation.json_object_valid and not validation.errors,
                )
            )
        return tuple(values)

    def validate(self, data_root: Path, relative_path: Path):
        return validate_profile_reference(data_root, relative_path)

    def import_profile(
        self,
        source: Path,
        data_root: Path,
        *,
        overwrite: bool,
    ) -> Path:
        if source.suffix.casefold() != ".json":
            raise ValueError("Recorder profile harus berupa file JSON.")
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Recorder profile bukan JSON yang valid.") from exc
        if not isinstance(value, dict):
            raise ValueError("Recorder profile harus berisi JSON object.")
        safe_name = Path(source.name).name
        if safe_name != source.name or safe_name in {"", ".", ".."}:
            raise ValueError("Nama recorder profile tidak aman.")
        target_root = resolve_storage_layout(data_root).hris_recorder_profiles_root
        if not target_root.is_dir():
            raise FileNotFoundError(
                "Folder recorder profile belum tersedia; initialize Data Root dulu."
            )
        target = target_root / safe_name
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        shutil.copy2(source, target)
        relative = to_relative_profile_path(data_root, target)
        validation = validate_profile_reference(data_root, relative)
        if validation.errors or not validation.json_object_valid:
            target.unlink(missing_ok=True)
            raise ValueError("Recorder profile hasil salin tidak valid.")
        return relative

    @staticmethod
    def remove_reference(relative_path: Path) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Reference harus berupa relative path yang aman.")
        return relative_path
