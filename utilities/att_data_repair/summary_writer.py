"""Atomic summary.json writer for Att Data Repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utilities.att_data_repair.models import SummaryWriteError


class AttDataRepairSummaryWriter:
    """Write readable UTF-8 JSON summaries atomically."""

    def write(self, path: str | Path, payload: dict[str, Any]) -> Path:
        """Write payload to summary.json via a temporary file."""

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        try:
            text = json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            temporary.write_text(text + "\n", encoding="utf-8")
            temporary.replace(target)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise SummaryWriteError(
                f"Gagal menulis summary Att Data Repair: {target}: {exc}"
            ) from exc
        return target
