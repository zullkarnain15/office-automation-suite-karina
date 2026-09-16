"""Pure headless tests for lazy loading and page lifecycle."""

from __future__ import annotations

import logging

import pytest

from ui.models import PageDefinition
from ui.navigation import NavigationController
from ui.page_registry import PageRegistry

from .conftest import FakeHost, FakePage


def test_initial_navigation_only_creates_dashboard(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    assert controller.navigate("dashboard")
    assert navigation_bundle["factory_calls"] == ["dashboard"]
    assert controller.cached_page_ids == ("dashboard",)


def test_target_page_is_created_lazily(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller.navigate("attendance")
    assert navigation_bundle["factory_calls"] == [
        "dashboard",
        "attendance",
    ]


def test_page_cache_prevents_recreation(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller.navigate("attendance")
    controller.navigate("dashboard")
    assert navigation_bundle["factory_calls"].count("dashboard") == 1


def test_on_hide_is_called(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller.navigate("attendance")
    assert "hide:dashboard" in navigation_bundle["events"]


def test_on_show_is_called(navigation_bundle) -> None:
    navigation_bundle["controller"].navigate("dashboard")
    assert "show:dashboard" in navigation_bundle["events"]


def test_navigation_can_be_cancelled(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    dashboard = controller._cache["dashboard"]
    dashboard.allow_navigation = False
    assert not controller.navigate("attendance")
    assert controller.active_page_id == "dashboard"
    assert navigation_bundle["factory_calls"] == ["dashboard"]


def test_active_page_changes(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller.navigate("attendance")
    assert controller.active_page_id == "attendance"
    assert navigation_bundle["active"][-1] == "attendance"


def test_header_metadata_changes(navigation_bundle) -> None:
    navigation_bundle["controller"].navigate("attendance")
    assert navigation_bundle["headers"][-1].title == "Attendance"
    assert "attendance" in navigation_bundle["headers"][-1].subtitle


def test_status_metadata_changes(navigation_bundle) -> None:
    navigation_bundle["controller"].navigate("dashboard")
    status = navigation_bundle["statuses"][-1]
    assert status.message == "Ready"
    assert status.selected_page == "Dashboard"


def test_factory_error_uses_error_page(app_context) -> None:
    events: list[str] = []

    def fail(parent, context):
        raise RuntimeError("factory failed")

    registry = PageRegistry(
        [PageDefinition("broken", "Broken", "Broken page", "error.ico", fail)]
    )
    controller = NavigationController(
        registry,
        object(),
        app_context,
        FakeHost(events),
        error_factory=lambda page, error: FakePage("safe-error", events),
        header_callback=lambda value: None,
        status_callback=lambda value: events.append(value.message),
        active_callback=lambda value: None,
        logger=logging.getLogger("factory-test"),
    )
    assert controller.navigate("broken")
    assert controller.active_page_id == "broken"
    assert "Gagal membuka halaman" in events
    assert "show:safe-error" in events


def test_unknown_page_has_clear_error(navigation_bundle) -> None:
    with pytest.raises(KeyError, match="Unknown page ID"):
        navigation_bundle["controller"].navigate("missing")


def test_same_page_navigation_is_noop(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    before = list(navigation_bundle["events"])
    assert controller.navigate("dashboard")
    assert navigation_bundle["events"] == before


def test_close_disposes_cached_pages(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller.navigate("attendance")
    assert controller.close()
    assert "dispose:dashboard" in navigation_bundle["events"]
    assert "dispose:attendance" in navigation_bundle["events"]
    assert controller.cached_page_ids == ()


def test_close_can_be_cancelled(navigation_bundle) -> None:
    controller = navigation_bundle["controller"]
    controller.navigate("dashboard")
    controller._cache["dashboard"].allow_navigation = False
    assert not controller.close()
    assert controller.active_page_id == "dashboard"
