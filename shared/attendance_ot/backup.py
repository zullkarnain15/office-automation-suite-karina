"""Verified SQLite backup scoped to the analytics database."""

import sqlite3
import uuid
from pathlib import Path


def verified_backup(database: Path, label: str) -> Path:
    destination = database.with_name(f"attendance_ot.{label}.{uuid.uuid4().hex}.bak")
    try:
        with sqlite3.connect(
            f"{database.resolve().as_uri()}?mode=ro", uri=True
        ) as source:
            with sqlite3.connect(destination) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup analytics gagal integrity check.")
        return destination
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
