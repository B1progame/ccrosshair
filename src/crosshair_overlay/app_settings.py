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
class BetaZoomSettings:
    sidebar_enabled: bool = False
    live_enabled: bool = False
    zoom_enabled: bool = False
    hotkey_sequence: str = "CTRL+ALT+Z"
    display_mode: str = "monitor"
    target_monitor_id: str = "same_as_game"
    position_x_percent: int = 50
    position_y_percent: int = 50
    zoom_percent: int = 200
    animation_enabled: bool = False
    animation_duration_ms: int = 180


@dataclass
class AppSettings:
    theme_mode: str = ThemeMode.SYSTEM.value
    accent_color: str = "#A923E2"
    selected_style_id: str = "classic_cross"
    overlay_enabled: bool = True
    sidebar_collapsed: bool = False
    selected_size_percent: int = 100
    global_size_percent: int = 100
    crosshair_storage_path: str = ""
    favorite_style_ids: list[str] = field(default_factory=list)
    auto_enable_on_fullscreen: bool = False
    auto_switch_game_profiles: bool = True
    auto_update_on_startup: bool = False
    run_on_startup_tray: bool = False
    game_profiles: list[GameProfile] = field(default_factory=list)
    beta_zoom: BetaZoomSettings = field(default_factory=BetaZoomSettings)

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
        safe["auto_update_on_startup"] = bool(safe.get("auto_update_on_startup", False))
        safe["run_on_startup_tray"] = bool(safe.get("run_on_startup_tray", False))

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

        raw_beta = safe.get("beta_zoom", {})
        if not isinstance(raw_beta, dict):
            raw_beta = {}
        hotkey_sequence = "CTRL+ALT+Z"
        if "hotkey_sequence" in raw_beta:
            hotkey_sequence = str(raw_beta.get("hotkey_sequence", "")).strip()
        display_mode = str(raw_beta.get("display_mode", "monitor")).strip().lower() or "monitor"
        if display_mode not in {"crosshair", "monitor"}:
            display_mode = "monitor"
        safe["beta_zoom"] = BetaZoomSettings(
            sidebar_enabled=bool(raw_beta.get("sidebar_enabled", False)),
            live_enabled=bool(raw_beta.get("live_enabled", False)),
            zoom_enabled=bool(raw_beta.get("zoom_enabled", False)),
            hotkey_sequence=hotkey_sequence,
            display_mode=display_mode,
            target_monitor_id=str(raw_beta.get("target_monitor_id", "same_as_game")).strip() or "same_as_game",
            position_x_percent=max(0, min(100, int(raw_beta.get("position_x_percent", 50)))),
            position_y_percent=max(0, min(100, int(raw_beta.get("position_y_percent", 50)))),
            zoom_percent=max(200, min(10000, int(raw_beta.get("zoom_percent", 200)))),
            animation_enabled=bool(raw_beta.get("animation_enabled", False)),
            animation_duration_ms=max(0, min(5000, int(raw_beta.get("animation_duration_ms", 180)))),
        )

        return cls(**safe)
