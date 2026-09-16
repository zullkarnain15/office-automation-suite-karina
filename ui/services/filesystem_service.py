"""Guarded Windows folder opening and safe file copy helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class FileSystemService:
    def open_folder(self, path: Path) -> bool:
        target = path if path.is_dir() else path.parent
        if not target.is_dir():
            return False
        if sys.platform != "win32" or not hasattr(os, "startfile"):
            return False
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except OSError:
            return False
        return True
