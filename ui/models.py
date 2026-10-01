"""Pure metadata models for the UI shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

PageFactory = Callable[[Any, Any], Any]


@dataclass(frozen=True, slots=True)
class PageDefinition:
    page_id: str
    title: str
    subtitle: str
    icon_name: str
    factory: PageFactory

    def __post_init__(self) -> None:
        for field_name in ("page_id", "title", "subtitle", "icon_name"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be empty.")
        if not callable(self.factory):
            raise TypeError("factory must be callable.")


@dataclass(frozen=True, slots=True)
class HeaderMetadata:
    title: str
    subtitle: str
    application_status: str = "Siap"


@dataclass(frozen=True, slots=True)
class StatusMetadata:
    message: str
    selected_page: str
    storage_status: str = "Database: Belum diperiksa"


class PageLoadError(RuntimeError):
    def __init__(self, page_id: str, cause: Exception) -> None:
        super().__init__(f"Halaman '{page_id}' gagal dibuat.")
        self.page_id = page_id
        self.cause = cause
