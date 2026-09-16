"""Tests for Karina's local-only presentation preferences."""

from __future__ import annotations

from shared.storage.registry import FakeRegistryBackend
from ui.services.karina_mascot_preferences import (
    KEY,
    KarinaMascotPreferences,
    KarinaMascotPreferencesService,
)


def test_karina_preferences_default_to_enabled_normal_mode() -> None:
    preferences = KarinaMascotPreferencesService(FakeRegistryBackend()).load()

    assert preferences == KarinaMascotPreferences()


def test_karina_preferences_are_saved_in_a_separate_local_key() -> None:
    backend = FakeRegistryBackend()
    service = KarinaMascotPreferencesService(backend)

    saved = service.save(KarinaMascotPreferences(False, False, "reduced"))

    assert saved == KarinaMascotPreferences(False, False, "reduced")
    assert backend.values[KEY] == {
        "KarinaMascotEnabled": "0",
        "KarinaMascotGreeting": "0",
        "KarinaMascotAnimationMode": "reduced",
    }
    assert service.load() == saved


def test_karina_preferences_normalize_unknown_animation_mode() -> None:
    value = KarinaMascotPreferences.normalized(True, True, "fast")

    assert value == KarinaMascotPreferences()
