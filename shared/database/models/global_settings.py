"""Typed global output and period settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlobalSettings:
    """The singleton global output root and optional date period."""

    output_root: str
    period_start: str | None
    period_end: str | None
    updated_at: str
    updated_by: str | None = None
    global_settings_id: int = 1
