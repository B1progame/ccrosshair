from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class ThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class GameProfile:
    game_id: str
    title: str
    source: str
    executable_names: list[str] = field(default_factory=list)
    executable_path: str = ""
    icon_path: str = ""
    style_id: str = ""
    enabled: bool = False


@dataclass
class AppSettings:
    theme_mode: str = ThemeMode.SYSTEM.value
    accent_color: str = "#4A90E2"
    selected_style_id: str = "classic_cross"
    overlay_enabled: bool = True
    sidebar_collapsed: bool = False
    selected_size_percent: int = 100
    global_size_percent: int = 100
    crosshair_storage_path: str = ""
    favorite_style_ids: list[str] = field(default_factory=list)
    auto_enable_on_fullscreen: bool = False
    auto_switch_game_profiles: bool = True
    game_profiles: list[GameProfile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        defaults = cls()
        safe = defaults.to_dict()
        safe.update({k: v for k, v in data.items() if k in safe})

        raw_favorites = safe.get("favorite_style_ids", [])
        if not isinstance(raw_favorites, list):
            raw_favorites = []
        safe["favorite_style_ids"] = [str(x) for x in raw_favorites]

        safe["auto_enable_on_fullscreen"] = bool(safe.get("auto_enable_on_fullscreen", False))
        safe["auto_switch_game_profiles"] = bool(safe.get("auto_switch_game_profiles", True))

        raw_profiles = safe.get("game_profiles", [])
        profiles: list[GameProfile] = []
        if isinstance(raw_profiles, list):
            for raw in raw_profiles:
                if not isinstance(raw, dict):
                    continue
                names = raw.get("executable_names", [])
                if not isinstance(names, list):
                    names = []
                normalized_names = [str(name).strip().lower() for name in names if str(name).strip()]
                profiles.append(
                    GameProfile(
                        game_id=str(raw.get("game_id", "")).strip(),
                        title=str(raw.get("title", "")).strip(),
                        source=str(raw.get("source", "")).strip() or "manual",
                        executable_names=normalized_names,
                        executable_path=str(raw.get("executable_path", "")).strip(),
                        icon_path=str(raw.get("icon_path", "")).strip(),
                        style_id=str(raw.get("style_id", "")).strip(),
                        enabled=bool(raw.get("enabled", False)),
                    )
                )
        safe["game_profiles"] = profiles

        return cls(**safe)
