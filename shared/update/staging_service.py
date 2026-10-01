"""Safe staging extraction for validated OAS-K update packages."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from shared.update.exceptions import UpdateStagingError
from shared.update.models import UpdatePackageInfo
from shared.update.package_validator import CHECKSUMS_PATH

UPDATE_DIRECTORY = "update"
DOWNLOADED_DIRECTORY = "downloaded"
STAGING_DIRECTORY = "staging"
ROLLBACK_DIRECTORY = "rollback"
LOGS_DIRECTORY = "logs"


class UpdateStagingService:
    """Create update folders and extract only already validated packages."""

    def ensure_update_layout(self, data_root: str | Path) -> dict[str, Path]:
        root = Path(data_root)
        update_root = root / UPDATE_DIRECTORY
        layout = {
            "downloaded": update_root / DOWNLOADED_DIRECTORY,
            "staging": update_root / STAGING_DIRECTORY,
            "rollback": update_root / ROLLBACK_DIRECTORY,
            "logs": update_root / LOGS_DIRECTORY,
        }
        for path in layout.values():
            path.mkdir(parents=True, exist_ok=True)
        return layout

    def stage(self, package_info: UpdatePackageInfo, data_root: str | Path) -> Path:
        layout = self.ensure_update_layout(data_root)
        final = layout["staging"] / f"v{package_info.manifest.version}"
        temp_parent = layout["staging"]
        temp_path: Path | None = None
        try:
            temp_path = Path(
                tempfile.mkdtemp(
                    prefix=f".v{package_info.manifest.version}.",
                    dir=temp_parent,
                )
            )
            self._extract(package_info.package_path, temp_path)
            if final.exists():
                shutil.rmtree(final)
            os.replace(temp_path, final)
            temp_path = None
            return final
        except Exception as exc:
            if temp_path is not None and temp_path.exists():
                shutil.rmtree(temp_path, ignore_errors=True)
            if not isinstance(exc, UpdateStagingError):
                raise UpdateStagingError(f"Staging update gagal: {exc}") from exc
            raise

    @staticmethod
    def _extract(package_path: Path, destination: Path) -> None:
        destination_resolved = destination.resolve()
        with zipfile.ZipFile(package_path) as archive:
            for item in archive.infolist():
                if item.is_dir() or item.filename == CHECKSUMS_PATH:
                    continue
                target = destination / item.filename
                resolved = target.resolve()
                if destination_resolved not in (resolved, *resolved.parents):
                    raise UpdateStagingError(
                        f"Archive entry keluar dari staging: {item.filename}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
