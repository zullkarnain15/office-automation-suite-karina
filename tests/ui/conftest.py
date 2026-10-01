"""Pure navigation fixtures and optional Tk root."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

import pytest

from ui.context import AppContext
from ui.models import PageDefinition
from ui.navigation import NavigationController
from ui.page_registry import PageRegistry


class FakePage:
    def __init__(
        self,
        page_id: str,
        events: list[str],
        *,
        allow_navigation: bool = True,
    ) -> None:
        self.page_id = page_id
        self.events = events
        self.allow_navigation = allow_navigation

    def on_show(self) -> None:
        self.events.append(f"show:{self.page_id}")

    def on_hide(self) -> None:
        self.events.append(f"hide:{self.page_id}")

    def can_navigate_away(self) -> bool:
        self.events.append(f"can_leave:{self.page_id}")
        return self.allow_navigation

    def can_close(self) -> bool:
        self.events.append(f"can_close:{self.page_id}")
        return self.allow_navigation

    def dispose(self) -> None:
        self.events.append(f"dispose:{self.page_id}")


class FakeHost:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def show_page(self, page: FakePage) -> None:
        self.events.append(f"host_show:{page.page_id}")

    def hide_page(self, page: FakePage) -> None:
        self.events.append(f"host_hide:{page.page_id}")


@pytest.fixture
def app_context(tmp_path: Path) -> AppContext:
    return AppContext(
        project_root=tmp_path,
        assets_path=tmp_path / "assets",
        application_version="ui1-test",
        logger=logging.getLogger("ui1-test"),
    )


@pytest.fixture
def navigation_bundle(app_context: AppContext):
    events: list[str] = []
    factory_calls: list[str] = []
    headers = []
    statuses = []
    active = []

    def definition(page_id: str) -> PageDefinition:
        def factory(parent, context):
            factory_calls.append(page_id)
            return FakePage(page_id, events)

        return PageDefinition(
            page_id,
            page_id.title(),
            f"Subtitle {page_id}",
            f"{page_id}.ico",
            factory,
        )

    registry = PageRegistry(
        [definition("dashboard"), definition("attendance")]
    )
    controller = NavigationController(
        registry,
        object(),
        app_context,
        FakeHost(events),
        error_factory=lambda page, error: FakePage(
            f"error-{page.page_id}",
            events,
        ),
        header_callback=headers.append,
        status_callback=statuses.append,
        active_callback=active.append,
    )
    return {
        "controller": controller,
        "events": events,
        "factory_calls": factory_calls,
        "headers": headers,
        "statuses": statuses,
        "active": active,
    }


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display is unavailable: {exc}")
    root.withdraw()
    yield root
    try:
        if root.winfo_exists():
            root.destroy()
    except tk.TclError:
        pass
