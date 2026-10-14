"""Pure cached page navigation and lifecycle coordination."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from ui.models import HeaderMetadata, PageDefinition, PageLoadError, StatusMetadata
from ui.page_registry import PageRegistry


class PageHost(Protocol):
    def show_page(self, page: Any) -> None: ...

    def hide_page(self, page: Any) -> None: ...


ErrorFactory = Callable[[PageDefinition, PageLoadError], Any]
HeaderCallback = Callable[[HeaderMetadata], None]
StatusCallback = Callable[[StatusMetadata], None]
ActiveCallback = Callable[[str], None]


class NavigationController:
    def __init__(
        self,
        registry: PageRegistry,
        parent: Any,
        context: Any,
        host: PageHost,
        *,
        error_factory: ErrorFactory,
        header_callback: HeaderCallback,
        status_callback: StatusCallback,
        active_callback: ActiveCallback,
        logger: logging.Logger | None = None,
    ) -> None:
        self.registry = registry
        self.parent = parent
        self.context = context
        self.host = host
        self.error_factory = error_factory
        self.header_callback = header_callback
        self.status_callback = status_callback
        self.active_callback = active_callback
        self.logger = logger or logging.getLogger(__name__)
        self._cache: dict[str, Any] = {}
        self._load_errors: set[str] = set()
        self._active_page_id: str | None = None

    @property
    def active_page_id(self) -> str | None:
        return self._active_page_id

    @property
    def cached_page_ids(self) -> tuple[str, ...]:
        return tuple(self._cache)

    def navigate(self, page_id: str) -> bool:
        definition = self.registry.get(page_id)
        if page_id == self._active_page_id:
            return True

        current = (
            self._cache.get(self._active_page_id)
            if self._active_page_id is not None
            else None
        )
        if current is not None:
            current.on_hide()
            if not current.can_navigate_away():
                current.on_show()
                self.status_callback(
                    StatusMetadata(
                        message="Navigasi dibatalkan oleh halaman aktif",
                        selected_page=self.registry.get(self._active_page_id).title,
                    )
                )
                return False

        target = self._cache.get(page_id)
        if target is None:
            target = self._create_page(definition)
            self._cache[page_id] = target

        if current is not None:
            self.host.hide_page(current)
        self.host.show_page(target)
        target.on_show()
        self._active_page_id = page_id
        self.header_callback(HeaderMetadata(definition.title, definition.subtitle))
        self.status_callback(
            StatusMetadata(
                message=(
                    "Gagal membuka halaman" if page_id in self._load_errors else "Ready"
                ),
                selected_page=definition.title,
            )
        )
        self.active_callback(page_id)
        return True

    def close(self) -> bool:
        active = (
            self._cache.get(self._active_page_id)
            if self._active_page_id is not None
            else None
        )
        if active is not None:
            can_close = getattr(
                active,
                "can_close",
                active.can_navigate_away,
            )
            if not can_close():
                return False
        for page in tuple(self._cache.values()):
            try:
                page.dispose()
            except Exception:
                self.logger.exception("Page dispose failed.")
        self._cache.clear()
        self._active_page_id = None
        return True

    def _create_page(self, definition: PageDefinition) -> Any:
        try:
            return definition.factory(self.parent, self.context)
        except Exception as exc:
            error = PageLoadError(definition.page_id, exc)
            self.logger.exception(
                "Unable to create UI page: %s",
                definition.page_id,
            )
            self.status_callback(
                StatusMetadata(
                    message="Gagal membuka halaman",
                    selected_page=definition.title,
                )
            )
            self._load_errors.add(definition.page_id)
            return self.error_factory(definition, error)
