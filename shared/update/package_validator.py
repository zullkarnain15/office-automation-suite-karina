"""Validation for OAS-K manual application update ZIP packages."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from dataclasses import fields
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from shared.database.constants import SCHEMA_VERSION
from shared.update.models import (
    APPLICATION_ID,
    APPLICATION_NAME,
    ENTRY_EXECUTABLE,
    PACKAGE_TYPE_APPLICATION_ONLY,
    SUPPORTED_PACKAGE_FORMATS,
    UpdatePackageInfo,
    UpdatePackageManifest,
    UpdateValidationResult,
)

MAX_FILE_COUNT = 5_000
MAX_TOTAL_UNCOMPRESSED_SIZE = 750 * 1024 * 1024
MANIFEST_PATH = "manifest.json"
CHECKSUMS_PATH = "checksums.sha256"
EXECUTABLE_PATH = f"application/{ENTRY_EXECUTABLE}"

_SENSITIVE_DIR_NAMES = {
    "database",
    "data",
    "recorder_profiles",
    "logs",
    "backup",
    "backups",
    "output",
}
_SENSITIVE_SUFFIXES = {".db", ".mdb"}
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


class UpdatePackageValidator:
    """Validate the full package before any extraction is attempted."""

    def __init__(
        self,
        *,
        supported_formats: frozenset[int] = SUPPORTED_PACKAGE_FORMATS,
        active_schema_version: int = SCHEMA_VERSION,
        max_file_count: int = MAX_FILE_COUNT,
        max_total_uncompressed_size: int = MAX_TOTAL_UNCOMPRESSED_SIZE,
    ) -> None:
        self.supported_formats = supported_formats
        self.active_schema_version = active_schema_version
        self.max_file_count = max_file_count
        self.max_total_uncompressed_size = max_total_uncompressed_size

    def validate(
        self,
        package_path: str | Path,
        *,
        current_version: str,
    ) -> UpdateValidationResult:
        path = Path(package_path)
        errors: list[str] = []
        warnings: list[str] = []

        if path.name != f"OAS-K_Update_v{path.stem.removeprefix('OAS-K_Update_v')}.zip":
            warnings.append("Nama file tidak mengikuti format OAS-K_Update_v<version>.zip.")
        if not path.is_file():
            return UpdateValidationResult(False, (f"Package tidak ditemukan: {path}",))
        if not zipfile.is_zipfile(path):
            return UpdateValidationResult(False, ("File bukan ZIP valid.",))

        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                self._validate_entries(entries, errors)
                manifest = self._read_manifest(archive, errors)
                checksums = self._read_checksums(archive, errors)
                if manifest is not None:
                    self._validate_manifest(manifest, current_version, errors)
                self._validate_checksum_matches(archive, entries, checksums, errors)
                file_count = sum(1 for item in entries if not item.is_dir())
                total_size = sum(item.file_size for item in entries if not item.is_dir())
                if file_count > self.max_file_count:
                    errors.append(
                        f"Jumlah file melebihi batas aman: {file_count} > {self.max_file_count}."
                    )
                if total_size > self.max_total_uncompressed_size:
                    errors.append(
                        "Ukuran ekstraksi melebihi batas aman: "
                        f"{total_size} > {self.max_total_uncompressed_size} bytes."
                    )
        except zipfile.BadZipFile:
            return UpdateValidationResult(False, ("ZIP rusak atau tidak dapat dibaca.",))
        except OSError as exc:
            return UpdateValidationResult(False, (f"Package tidak dapat dibaca: {exc}",))

        if errors or manifest is None:
            return UpdateValidationResult(False, tuple(errors), tuple(warnings))
        return UpdateValidationResult(
            True,
            (),
            tuple(warnings),
            UpdatePackageInfo(
                package_path=path,
                manifest=manifest,
                package_sha256=_sha256(path),
                file_count=file_count,
                total_uncompressed_size=total_size,
            ),
        )

    def _validate_entries(self, entries: list[zipfile.ZipInfo], errors: list[str]) -> None:
        seen: set[str] = set()
        names = {item.filename for item in entries}
        if MANIFEST_PATH not in names:
            errors.append("manifest.json wajib ada.")
        if CHECKSUMS_PATH not in names:
            errors.append("checksums.sha256 wajib ada.")
        if EXECUTABLE_PATH not in names:
            errors.append(f"{EXECUTABLE_PATH} wajib tersedia.")
        if not any(item.filename.rstrip("/") == "application" for item in entries):
            errors.append("Folder application/ wajib ada.")

        for item in entries:
            name = item.filename
            normalized = name.replace("\\", "/")
            lowered = normalized.casefold().rstrip("/")
            if lowered in seen:
                errors.append(f"Duplicate archive path ditolak: {name}")
            seen.add(lowered)
            if normalized != name:
                errors.append(f"Archive entry memakai separator tidak aman: {name}")
            if self._is_unsafe_path(normalized):
                errors.append(f"Archive path tidak aman: {name}")
            if self._is_sensitive_path(normalized):
                errors.append(f"Archive entry data sensitif ditolak: {name}")
            if self._is_symlink_like(item):
                errors.append(f"Archive entry symbolic-link-like ditolak: {name}")

    @staticmethod
    def _is_unsafe_path(name: str) -> bool:
        if not name or name.startswith("/"):
            return True
        if PureWindowsPath(name).drive:
            return True
        parts = PurePosixPath(name).parts
        return any(part in {"", ".", ".."} for part in parts)

    @staticmethod
    def _is_sensitive_path(name: str) -> bool:
        path = PurePosixPath(name)
        parts = {part.casefold() for part in path.parts}
        suffix = path.suffix.casefold()
        return bool(parts & _SENSITIVE_DIR_NAMES) or suffix in _SENSITIVE_SUFFIXES

    @staticmethod
    def _is_symlink_like(item: zipfile.ZipInfo) -> bool:
        mode = (item.external_attr >> 16) & 0xFFFF
        return stat.S_ISLNK(mode)

    def _read_manifest(
        self,
        archive: zipfile.ZipFile,
        errors: list[str],
    ) -> UpdatePackageManifest | None:
        try:
            with archive.open(MANIFEST_PATH) as handle:
                raw = json.loads(handle.read().decode("utf-8"))
        except KeyError:
            return None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"manifest.json tidak valid: {exc}")
            return None
        if not isinstance(raw, dict):
            errors.append("manifest.json harus berupa object JSON.")
            return None
        names = {field.name for field in fields(UpdatePackageManifest)}
        missing = sorted(names - set(raw))
        if missing:
            errors.append("manifest.json kehilangan field: " + ", ".join(missing))
            return None
        try:
            return UpdatePackageManifest(**{name: raw[name] for name in names})
        except TypeError as exc:
            errors.append(f"manifest.json schema tidak valid: {exc}")
            return None

    def _validate_manifest(
        self,
        manifest: UpdatePackageManifest,
        current_version: str,
        errors: list[str],
    ) -> None:
        if manifest.application_id != APPLICATION_ID:
            errors.append("application_id wajib oas-k.")
        if manifest.application_name != APPLICATION_NAME:
            errors.append("application_name tidak cocok.")
        if manifest.package_format not in self.supported_formats:
            errors.append(f"package_format tidak didukung: {manifest.package_format}.")
        if not _valid_semver(manifest.version):
            errors.append(f"Target version bukan semantic version valid: {manifest.version}.")
        if not _valid_semver(manifest.minimum_current_version):
            errors.append(
                "minimum_current_version bukan semantic version valid: "
                f"{manifest.minimum_current_version}."
            )
        if _valid_semver(manifest.version) and _valid_semver(current_version):
            if _compare_semver(manifest.version, current_version) <= 0:
                errors.append("Target version harus lebih tinggi dari current version.")
        if _valid_semver(manifest.minimum_current_version) and _valid_semver(current_version):
            if _compare_semver(current_version, manifest.minimum_current_version) < 0:
                errors.append(
                    "Current version lebih rendah dari minimum_current_version package."
                )
        if manifest.package_type != PACKAGE_TYPE_APPLICATION_ONLY:
            errors.append("package_type wajib application_only.")
        if manifest.migration_required is True:
            if manifest.database_schema_to != SCHEMA_VERSION:
                errors.append(
                    "Target schema package tidak sesuai aplikasi: "
                    f"{manifest.database_schema_to} != {SCHEMA_VERSION}."
                )
            if manifest.database_schema_from > manifest.database_schema_to:
                errors.append("database_schema_from tidak boleh lebih tinggi dari database_schema_to.")
            if not (
                manifest.database_schema_from
                <= self.active_schema_version
                <= manifest.database_schema_to
            ):
                errors.append(
                    "Database schema package tidak kompatibel dengan database aktif: "
                    f"{manifest.database_schema_from}-{manifest.database_schema_to} "
                    f"tidak mencakup {self.active_schema_version}."
                )
        elif manifest.migration_required is False:
            if manifest.database_schema_from != manifest.database_schema_to:
                errors.append("database_schema_from harus sama dengan database_schema_to.")
            if manifest.database_schema_from != self.active_schema_version:
                errors.append(
                    "Database schema package tidak kompatibel dengan database aktif: "
                    f"{manifest.database_schema_from} != {self.active_schema_version}."
                )
        else:
            errors.append("migration_required wajib boolean.")
        if manifest.entry_executable != ENTRY_EXECUTABLE:
            errors.append(f"entry_executable wajib {ENTRY_EXECUTABLE}.")
        try:
            created = datetime.fromisoformat(manifest.created_at)
            if created.tzinfo is None or created.tzinfo.utcoffset(created) is None:
                errors.append("created_at wajib ISO-8601 timezone-aware.")
        except (TypeError, ValueError):
            errors.append("created_at wajib ISO-8601 valid.")

    def _read_checksums(
        self,
        archive: zipfile.ZipFile,
        errors: list[str],
    ) -> dict[str, str]:
        try:
            text = archive.read(CHECKSUMS_PATH).decode("utf-8")
        except KeyError:
            return {}
        except UnicodeDecodeError as exc:
            errors.append(f"checksums.sha256 bukan UTF-8 valid: {exc}")
            return {}
        checksums: dict[str, str] = {}
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                errors.append(f"Format checksum tidak valid pada baris {line_number}.")
                continue
            name = parts[1].lstrip("*").strip()
            if self._is_unsafe_path(name):
                errors.append(f"Path checksum tidak aman: {name}")
                continue
            checksums[name.replace("\\", "/")] = parts[0].casefold()
        return checksums

    def _validate_checksum_matches(
        self,
        archive: zipfile.ZipFile,
        entries: list[zipfile.ZipInfo],
        checksums: dict[str, str],
        errors: list[str],
    ) -> None:
        archive_file_names: set[str] = set()
        for item in entries:
            if item.is_dir() or item.filename == CHECKSUMS_PATH:
                continue
            archive_file_names.add(item.filename)
            expected = checksums.get(item.filename)
            if expected is None:
                errors.append(f"Checksum hilang untuk {item.filename}.")
                continue
            digest = hashlib.sha256()
            with archive.open(item) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual = digest.hexdigest()
            if actual != expected:
                errors.append(f"Checksum tidak cocok untuk {item.filename}.")
        for name in sorted(set(checksums) - archive_file_names):
            errors.append(f"Checksum menunjuk file yang tidak ada di archive: {name}.")


def _valid_semver(value: Any) -> bool:
    return isinstance(value, str) and _SEMVER.fullmatch(value) is not None


def _semver_core(value: str) -> tuple[int, int, int]:
    core = re.split(r"[-+]", value, maxsplit=1)[0]
    major, minor, patch = core.split(".")
    return int(major), int(minor), int(patch)


def _compare_semver(left: str, right: str) -> int:
    left_core = _semver_core(left)
    right_core = _semver_core(right)
    return (left_core > right_core) - (left_core < right_core)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
