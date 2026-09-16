"""Local HKCU-backed preferences for the optional Karina UI component."""

from __future__ import annotations

from dataclasses import dataclass

from shared.storage.exceptions import RegistryAccessError

KEY = r"Software\OTO Finance\OAS-K\Preferences"


@dataclass(frozen=True)
class KarinaMascotPreferences:
    enabled: bool = True
    greeting_enabled: bool = True
    animation_mode: str = "normal"

    @classmethod
    def normalized(cls, enabled, greeting_enabled, animation_mode) -> "KarinaMascotPreferences":
        mode = str(animation_mode or "normal").casefold()
        return cls(bool(enabled), bool(greeting_enabled), mode if mode in {"normal", "reduced", "static"} else "normal")


class KarinaMascotPreferencesService:
    def __init__(self, backend) -> None:
        self.backend = backend

    def load(self) -> KarinaMascotPreferences:
        try:
            return KarinaMascotPreferences.normalized(
                self.backend.read_value(KEY, "KarinaMascotEnabled") != "0",
                self.backend.read_value(KEY, "KarinaMascotGreeting") != "0",
                self.backend.read_value(KEY, "KarinaMascotAnimationMode") or "normal",
            )
        except RegistryAccessError:
            return KarinaMascotPreferences()

    def save(self, value: KarinaMascotPreferences) -> KarinaMascotPreferences:
        value = KarinaMascotPreferences.normalized(
            value.enabled, value.greeting_enabled, value.animation_mode
        )
        self.backend.write_values(KEY, {
            "KarinaMascotEnabled": "1" if value.enabled else "0",
            "KarinaMascotGreeting": "1" if value.greeting_enabled else "0",
            "KarinaMascotAnimationMode": value.animation_mode,
        })
        return value
