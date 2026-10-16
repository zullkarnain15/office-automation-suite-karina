from __future__ import annotations

from ui.pages.settings.module_configuration_section import (
    ModuleConfigurationSection,
)


def test_loaded_module_configuration_does_not_refresh_when_reselected() -> None:
    section = object.__new__(ModuleConfigurationSection)
    calls = []
    section._loaded = True
    section.refresh = lambda: calls.append("refresh")

    section.on_selected()

    assert calls == []


def test_unloaded_module_configuration_refreshes_when_selected() -> None:
    section = object.__new__(ModuleConfigurationSection)
    calls = []
    section._loaded = False
    section.refresh = lambda: calls.append("refresh")

    section.on_selected()

    assert calls == ["refresh"]
