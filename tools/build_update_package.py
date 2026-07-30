"""Build a deterministic manual OAS-K application update package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.database.constants import SCHEMA_VERSION

APPLICATION_ID = "oas-k"
APPLICATION_NAME = "Office Automation Suite - Karina"
ENTRY_EXECUTABLE = "OAS-K.exe"
PACKAGE_FORMAT = 1
PACKAGE_TYPE = "application_only"
PROHIBITED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "backup",
    "backups",
    "cache",
    "database",
    "data",
    "dist-info",
    "logs",
    "output",
    "recorder_profiles",
}
PROHIBITED_SUFFIXES = {".db", ".mdb", ".sqlite", ".sqlite3", ".log", ".ini", ".env"}
PROHIBITED_NAMES = {
    "config.json",
    "local_config.json",
    "settings.json",
    "credentials.json",
    "token.json",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build OAS-K_Update_v<version>.zip from an application build folder."
    )
    parser.add_argument("--version", required=True, help="Target semantic version.")
    parser.add_argument(
        "--application-dir",
        required=True,
        type=Path,
        help="Directory containing the application build, including OAS-K.exe.",
    )
    parser.add_argument(
        "--release-notes",
        required=True,
        type=Path,
        help="UTF-8 release notes text file.",
    )
    parser.add_argument(
        "--minimum-current-version",
        default="1.0.0",
        help="Minimum current app version allowed to apply this update.",
    )
    parser.add_argument(
        "--schema-version",
        default=SCHEMA_VERSION,
        type=int,
        help="Database schema version this application-only package supports.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory where the ZIP and .sha256 file will be written.",
    )
    args = parser.parse_args(argv)

    try:
        package_path = build_update_package(
            version=args.version,
            application_dir=args.application_dir,
            release_notes=args.release_notes,
            minimum_current_version=args.minimum_current_version,
            schema_version=args.schema_version,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    digest = sha256_file(package_path)
    digest_path = package_path.with_suffix(package_path.suffix + ".sha256")
    digest_path.write_text(f"{digest}  {package_path.name}\n", encoding="utf-8")
    print(f"Package: {package_path}")
    print(f"SHA-256: {digest}")
    return 0


def build_update_package(
    *,
    version: str,
    application_dir: Path,
    release_notes: Path,
    minimum_current_version: str,
    schema_version: int,
    output_dir: Path,
) -> Path:
    application_dir = application_dir.resolve()
    release_notes = release_notes.resolve()
    output_dir = output_dir.resolve()
    if not application_dir.is_dir():
        raise ValueError(f"Application build directory tidak ditemukan: {application_dir}")
    if not (application_dir / ENTRY_EXECUTABLE).is_file():
        raise ValueError(f"{ENTRY_EXECUTABLE} wajib ada di application build directory.")
    if not release_notes.is_file():
        raise ValueError(f"Release notes tidak ditemukan: {release_notes}")
    unsafe = find_prohibited_paths(application_dir)
    if unsafe:
        sample = ", ".join(str(path.relative_to(application_dir)) for path in unsafe[:10])
        raise ValueError(f"Build directory mengandung file/folder sensitif: {sample}")

    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"OAS-K_Update_v{version}.zip"
    package_path = output_dir / package_name
    manifest = {
        "package_format": PACKAGE_FORMAT,
        "application_id": APPLICATION_ID,
        "application_name": APPLICATION_NAME,
        "version": version,
        "minimum_current_version": minimum_current_version,
        "package_type": PACKAGE_TYPE,
        "database_schema_from": schema_version,
        "database_schema_to": schema_version,
        "migration_required": False,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "entry_executable": ENTRY_EXECUTABLE,
    }
    with tempfile.TemporaryDirectory(prefix=".oas-k-update-", dir=output_dir) as temp_name:
        temp_root = Path(temp_name)
        manifest_path = temp_root / "manifest.json"
        notes_path = temp_root / "release_notes.txt"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        notes_path.write_text(
            release_notes.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        package_files: list[tuple[str, Path]] = [
            ("manifest.json", manifest_path),
            ("release_notes.txt", notes_path),
        ]
        for path in sorted(item for item in application_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(application_dir).as_posix()
            package_files.append((f"application/{relative}", path))
        checksums_path = temp_root / "checksums.sha256"
        checksums_path.write_text(
            "\n".join(
                f"{sha256_file(path)}  {archive_name}"
                for archive_name, path in sorted(package_files)
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temp_package = temp_root / package_name
        with zipfile.ZipFile(temp_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(_zip_info("application/"), b"")
            for archive_name, path in sorted(package_files):
                archive.writestr(_zip_info(archive_name), path.read_bytes())
            archive.writestr(_zip_info("checksums.sha256"), checksums_path.read_bytes())
        package_path.unlink(missing_ok=True)
        temp_package.replace(package_path)
    return package_path


def find_prohibited_paths(root: Path) -> list[Path]:
    unsafe: list[Path] = []
    for path in root.rglob("*"):
        parts = {part.casefold() for part in path.relative_to(root).parts}
        if parts & PROHIBITED_DIRS:
            unsafe.append(path)
            continue
        if path.is_file():
            name = path.name.casefold()
            if name in PROHIBITED_NAMES or path.suffix.casefold() in PROHIBITED_SUFFIXES:
                unsafe.append(path)
    return unsafe


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    if name.endswith("/"):
        info.external_attr = 0o755 << 16
    return info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
