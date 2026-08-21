"""Small dependency context passed to UI pages."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NavigationCallback = Callable[[str], bool]
StatusCallback = Callable[[str], None]
CloseCallback = Callable[[], bool]
MascotStartedCallback = Callable[[], None]
MascotFinishedCallback = Callable[[str | None], None]


@dataclass(slots=True)
class AppContext:
    project_root: Path
    assets_path: Path
    application_version: str
    logger: logging.Logger
    services: Mapping[str, Any] = field(default_factory=dict)
    app_services: Any | None = None
    navigate: NavigationCallback | None = None
    set_status: StatusCallback | None = None
    request_close: CloseCallback | None = None
    mascot_work_started: MascotStartedCallback | None = None
    mascot_work_finished: MascotFinishedCallback | None = None
    mascot_controller: Any | None = None
