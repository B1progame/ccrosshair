from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class ThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class GameLoadout:
    loadout_id: str
    name: str
    style_id: str
    zoom_percent: int = 200
    fire_pulse: bool = True
    fire_cadence_ms: int = 0
    fire_key_sequence: str = ""
    gap_expansion: bool = True
    opacity_pulse: bool = False
    hide_on_ads: bool = False
    fire_duration_ms: int = 120
    fire_amplitude_percent: int = 18
    ads_transition_ms: int = 80
    color_hex: str = ""
    opacity_percent: int = 100
    outline_color_hex: str = ""
    outline_opacity_percent: int = 100
    ads_style_id: str = ""
    ads_color_hex: str = ""
    ads_opacity_percent: int = 100
    ads_outline_color_hex: str = ""
    ads_outline_opacity_percent: int = 100


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
    loadouts: list[GameLoadout] = field(default_factory=list)
    active_loadout_id: str = ""


def _loadouts_from_data(raw: object, legacy_style_id: str) -> list[GameLoadout]:
    if not isinstance(raw, list):
        raw = []
    result: list[GameLoadout] = []
    seen: set[str] = set()

    def bounded(value: object, fallback: int, minimum: int, maximum: int) -> int:
        try:
            if isinstance(value, bool):
                return fallback
            return max(minimum, min(maximum, int(value)))
        except (TypeError, ValueError, OverflowError):
            return fallback

    def boolean(value: object, fallback: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        return fallback

    for index, item in enumerate(raw[:20]):
        if not isinstance(item, dict):
            continue
        loadout_id = str(item.get("loadout_id", "")).strip()[:64]
        if not loadout_id or loadout_id in seen:
            continue
        seen.add(loadout_id)
        result.append(GameLoadout(
            loadout_id=loadout_id,
            name=str(item.get("name", f"Loadout {index + 1}")).strip()[:64] or f"Loadout {index + 1}",
            style_id=str(item.get("style_id", "")).strip()[:256],
            zoom_percent=bounded(item.get("zoom_percent"), 200, 200, 1600),
            fire_pulse=boolean(item.get("fire_pulse"), True),
            fire_cadence_ms=bounded(item.get("fire_cadence_ms"), 0, 0, 1000),
            fire_key_sequence=str(item.get("fire_key_sequence", "")).strip()[:128],
            gap_expansion=boolean(item.get("gap_expansion"), True),
            opacity_pulse=boolean(item.get("opacity_pulse"), False),
            hide_on_ads=boolean(item.get("hide_on_ads"), False),
            fire_duration_ms=bounded(item.get("fire_duration_ms"), 120, 40, 1000),
            fire_amplitude_percent=bounded(item.get("fire_amplitude_percent"), 18, 0, 100),
            ads_transition_ms=bounded(item.get("ads_transition_ms"), 80, 0, 500),
            color_hex=_valid_optional_hex(item.get("color_hex")),
            opacity_percent=bounded(item.get("opacity_percent"), 100, 0, 100),
            outline_color_hex=_valid_optional_hex(item.get("outline_color_hex")),
            outline_opacity_percent=bounded(item.get("outline_opacity_percent"), 100, 0, 100),
            ads_style_id=str(item.get("ads_style_id", "")).strip()[:256],
            ads_color_hex=_valid_optional_hex(item.get("ads_color_hex")),
            ads_opacity_percent=bounded(item.get("ads_opacity_percent"), 100, 0, 100),
            ads_outline_color_hex=_valid_optional_hex(item.get("ads_outline_color_hex")),
            ads_outline_opacity_percent=bounded(item.get("ads_outline_opacity_percent"), 100, 0, 100),
        ))
    if not result and legacy_style_id:
        result.append(GameLoadout("default", "Default", legacy_style_id))
    return result


def _valid_optional_hex(value: object) -> str:
    if not isinstance(value, str) or (value and (len(value) != 7 or value[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in value[1:]))):
        return ""
    return value.upper()


@dataclass
class BetaZoomSettings:
    sidebar_enabled: bool = False
    live_enabled: bool = False
    zoom_enabled: bool = False
    hotkey_sequence: str = "N"
    activation_mode: str = "hold"
    display_mode: str = "monitor"
    target_monitor_id: str = "same_as_game"
    position_x_percent: int = 50
    position_y_percent: int = 50
    zoom_percent: int = 200
    runtime_mode: str = "balanced"
    auto_adapt_enabled: bool = False
    zoom_in_hotkey_sequence: str = "CTRL+ALT+RIGHT"
    zoom_out_hotkey_sequence: str = "CTRL+ALT+LEFT"
    zoom_reset_hotkey_sequence: str = "CTRL+ALT+HOME"
    animation_enabled: bool = False
    animation_duration_ms: int = 180
    consume_mouse_wheel: bool = False
    cleanup_enabled: bool = False
    cleanup_radius: int = 5
    cleanup_strength: int = 100
    cleanup_preview: bool = False
    hide_crosshair_when_zoomed: bool = False


@dataclass
class AccessibilitySettings:
    high_contrast: bool = False
    reduced_motion: bool = False
    density: str = "comfortable"
    text_scale: int = 100


@dataclass
class ReactiveSettings:
    enabled: bool = False
    fire_pulse: bool = True
    fire_cadence_ms: int = 0
    fire_key_sequence: str = ""
    gap_expansion: bool = True
    opacity_pulse: bool = False
    hide_on_ads: bool = False
    emergency_hotkey: str = "CTRL+ALT+H"
    fire_duration_ms: int = 120
    fire_amplitude_percent: int = 18
    ads_transition_ms: int = 80
    ads_mode: str = "hold"


@dataclass
class LibraryCollection:
    collection_id: str
    name: str
    style_ids: list[str] = field(default_factory=list)


@dataclass
class AppSettings:
    schema_version: int = 8
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
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    reactive: ReactiveSettings = field(default_factory=ReactiveSettings)
    recent_style_ids: list[str] = field(default_factory=list)
    recent_crosshair_colors: list[str] = field(default_factory=list)
    monitor_offsets: dict[str, dict[str, int]] = field(default_factory=dict)
    quick_switch_next_hotkey: str = "CTRL+ALT+UP"
    quick_switch_previous_hotkey: str = "CTRL+ALT+DOWN"
    quick_switch_favorite_hotkey: str = "CTRL+ALT+F"
    library_collections: list[LibraryCollection] = field(default_factory=list)
    library_tags: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        defaults = cls()
        if not isinstance(data, dict):
            return defaults
        safe = defaults.to_dict()
        safe.update({k: v for k, v in data.items() if k in safe})

        def bounded_int(value: object, fallback: int, minimum: int, maximum: int) -> int:
            try:
                if isinstance(value, bool):
                    return fallback
                return max(minimum, min(maximum, int(value)))
            except (TypeError, ValueError, OverflowError):
                return fallback

        def safe_bool(value: object, fallback: bool) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().casefold()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
            return fallback

        theme = str(safe.get("theme_mode", ThemeMode.SYSTEM.value)).lower()
        safe["theme_mode"] = theme if theme in {item.value for item in ThemeMode} else ThemeMode.SYSTEM.value
        accent = safe.get("accent_color")
        if not isinstance(accent, str) or len(accent) != 7 or not accent.startswith("#") or any(c not in "0123456789abcdefABCDEF" for c in accent[1:]):
            safe["accent_color"] = defaults.accent_color
        safe["schema_version"] = 8
        safe["selected_size_percent"] = bounded_int(safe.get("selected_size_percent"), 100, 50, 200)
        safe["global_size_percent"] = bounded_int(safe.get("global_size_percent"), 100, 50, 200)

        raw_favorites = safe.get("favorite_style_ids", [])
        if not isinstance(raw_favorites, list):
            raw_favorites = []
        safe["favorite_style_ids"] = [str(x) for x in raw_favorites]

        safe["auto_enable_on_fullscreen"] = safe_bool(safe.get("auto_enable_on_fullscreen"), False)
        safe["auto_switch_game_profiles"] = safe_bool(safe.get("auto_switch_game_profiles"), True)
        safe["auto_update_on_startup"] = safe_bool(safe.get("auto_update_on_startup"), False)
        safe["run_on_startup_tray"] = safe_bool(safe.get("run_on_startup_tray"), False)

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
                        enabled=safe_bool(raw.get("enabled"), False),
                        loadouts=_loadouts_from_data(raw.get("loadouts"), str(raw.get("style_id", ""))),
                        active_loadout_id=str(raw.get("active_loadout_id", "")).strip(),
                    )
                )
                profile = profiles[-1]
                if profile.loadouts:
                    active = next((item for item in profile.loadouts if item.loadout_id == profile.active_loadout_id), profile.loadouts[0])
                    profile.active_loadout_id = active.loadout_id
                    profile.style_id = active.style_id
        safe["game_profiles"] = profiles

        raw_beta = safe.get("beta_zoom", {})
        if not isinstance(raw_beta, dict):
            raw_beta = {}
        hotkey_sequence = "N"
        if "hotkey_sequence" in raw_beta:
            hotkey_sequence = str(raw_beta.get("hotkey_sequence", "")).strip()
            if hotkey_sequence.casefold() == "ctrl+alt+z":
                hotkey_sequence = "N"  # Replace the shipped default with the requested N shortcut.
        activation_mode = raw_beta.get("activation_mode", "hold")
        if activation_mode not in {"hold", "toggle"}:
            activation_mode = "hold"
        display_mode = str(raw_beta.get("display_mode", "monitor")).strip().lower() or "monitor"
        if display_mode not in {"crosshair", "monitor"}:
            display_mode = "monitor"
        runtime_mode = str(raw_beta.get("runtime_mode", "balanced")).strip().lower()
        if runtime_mode not in {"quiet", "eco", "fast", "balanced", "quality"}:
            runtime_mode = "balanced"
        zoom_hotkeys = {
            key: str(raw_beta.get(key, fallback)).strip()[:128]
            for key, fallback in (
                ("zoom_in_hotkey_sequence", "CTRL+ALT+RIGHT"),
                ("zoom_out_hotkey_sequence", "CTRL+ALT+LEFT"),
                ("zoom_reset_hotkey_sequence", "CTRL+ALT+HOME"),
            )
        }
        safe["beta_zoom"] = BetaZoomSettings(
            sidebar_enabled=safe_bool(raw_beta.get("sidebar_enabled"), False),
            live_enabled=safe_bool(raw_beta.get("live_enabled"), False),
            zoom_enabled=safe_bool(raw_beta.get("zoom_enabled"), False),
            hotkey_sequence=hotkey_sequence,
            activation_mode=activation_mode,
            display_mode=display_mode,
            target_monitor_id=str(raw_beta.get("target_monitor_id", "same_as_game")).strip() or "same_as_game",
            position_x_percent=bounded_int(raw_beta.get("position_x_percent", 50), 50, 0, 100),
            position_y_percent=bounded_int(raw_beta.get("position_y_percent", 50), 50, 0, 100),
            zoom_percent=bounded_int(raw_beta.get("zoom_percent", 200), 200, 200, 1600),
            runtime_mode=runtime_mode,
            auto_adapt_enabled=safe_bool(raw_beta.get("auto_adapt_enabled"), False),
            **zoom_hotkeys,
            animation_enabled=safe_bool(raw_beta.get("animation_enabled"), False),
            animation_duration_ms=bounded_int(raw_beta.get("animation_duration_ms", 180), 180, 0, 5000),
            consume_mouse_wheel=safe_bool(raw_beta.get("consume_mouse_wheel"), False),
            cleanup_enabled=safe_bool(raw_beta.get("cleanup_enabled"), False),
            cleanup_radius=bounded_int(raw_beta.get("cleanup_radius"), 5, 1, 24),
            cleanup_strength=bounded_int(raw_beta.get("cleanup_strength"), 100, 0, 100),
            cleanup_preview=safe_bool(raw_beta.get("cleanup_preview"), False),
            hide_crosshair_when_zoomed=safe_bool(raw_beta.get("hide_crosshair_when_zoomed"), False),
        )

        raw_accessibility = safe.get("accessibility", {})
        if not isinstance(raw_accessibility, dict):
            raw_accessibility = {}
        density = str(raw_accessibility.get("density", "comfortable")).lower()
        if density not in {"compact", "comfortable", "spacious"}:
            density = "comfortable"
        safe["accessibility"] = AccessibilitySettings(
            high_contrast=safe_bool(raw_accessibility.get("high_contrast"), False),
            reduced_motion=safe_bool(raw_accessibility.get("reduced_motion"), False),
            density=density,
            text_scale=bounded_int(raw_accessibility.get("text_scale"), 100, 80, 150),
        )
        raw_reactive = safe.get("reactive", {})
        if not isinstance(raw_reactive, dict):
            raw_reactive = {}
        safe["reactive"] = ReactiveSettings(
            enabled=safe_bool(raw_reactive.get("enabled"), False),
            fire_pulse=safe_bool(raw_reactive.get("fire_pulse"), True),
            fire_cadence_ms=bounded_int(raw_reactive.get("fire_cadence_ms", 0), 0, 0, 1000),
            fire_key_sequence=str(raw_reactive.get("fire_key_sequence", "")).strip()[:128],
            gap_expansion=safe_bool(raw_reactive.get("gap_expansion"), True),
            opacity_pulse=safe_bool(raw_reactive.get("opacity_pulse"), False),
            hide_on_ads=safe_bool(raw_reactive.get("hide_on_ads"), False),
            emergency_hotkey=str(raw_reactive.get("emergency_hotkey", "CTRL+ALT+H")).strip()[:128],
            fire_duration_ms=bounded_int(raw_reactive.get("fire_duration_ms", 120), 120, 40, 1000),
            fire_amplitude_percent=bounded_int(raw_reactive.get("fire_amplitude_percent", 18), 18, 0, 100),
            ads_transition_ms=bounded_int(raw_reactive.get("ads_transition_ms", 80), 80, 0, 500),
            ads_mode=raw_reactive.get("ads_mode", "hold").lower() if isinstance(raw_reactive.get("ads_mode", "hold"), str) and raw_reactive.get("ads_mode", "hold").lower() in {"hold", "toggle"} else "hold",
        )
        raw_recent = safe.get("recent_style_ids", [])
        safe["recent_style_ids"] = list(dict.fromkeys(str(x) for x in raw_recent if isinstance(x, str)))[:50] if isinstance(raw_recent, list) else []
        raw_colors = safe.get("recent_crosshair_colors", [])
        colors = []
        if isinstance(raw_colors, list):
            for value in raw_colors:
                if isinstance(value, str) and len(value) == 7 and value.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in value[1:]):
                    colors.append(value.upper())
        safe["recent_crosshair_colors"] = list(dict.fromkeys(colors))[:12]

        raw_offsets = safe.get("monitor_offsets", {})
        offsets: dict[str, dict[str, int]] = {}
        if isinstance(raw_offsets, dict):
            for monitor_id, raw_offset in list(raw_offsets.items())[:16]:
                if not isinstance(monitor_id, str) or not monitor_id.strip() or len(monitor_id) > 64 or not isinstance(raw_offset, dict):
                    continue
                x, y = raw_offset.get("x"), raw_offset.get("y")
                if type(x) is int and type(y) is int and -128 <= x <= 128 and -128 <= y <= 128:
                    offsets[monitor_id] = {"x": x, "y": y}
        safe["monitor_offsets"] = offsets

        raw_collections = safe.get("library_collections", [])
        collections: list[LibraryCollection] = []
        seen_collections: set[str] = set()
        if isinstance(raw_collections, list):
            for raw in raw_collections[:50]:
                if not isinstance(raw, dict):
                    continue
                collection_id = raw.get("collection_id", "")
                name = raw.get("name", "")
                raw_ids = raw.get("style_ids", [])
                if (not isinstance(collection_id, str) or not collection_id or len(collection_id) > 64
                        or collection_id in seen_collections or not isinstance(name, str) or not name.strip()
                        or len(name.strip()) > 64 or not isinstance(raw_ids, list)):
                    continue
                style_ids = list(dict.fromkeys(item.strip() for item in raw_ids[:500]
                                               if isinstance(item, str) and item.strip() and len(item) <= 256))
                collections.append(LibraryCollection(collection_id, name.strip(), style_ids))
                seen_collections.add(collection_id)
        safe["library_collections"] = collections

        raw_library_tags = safe.get("library_tags", {})
        library_tags: dict[str, list[str]] = {}
        total_tags = 0
        if isinstance(raw_library_tags, dict):
            for style_id, raw_tags in list(raw_library_tags.items())[:10000]:
                if not isinstance(style_id, str) or not style_id.strip() or len(style_id) > 256 or not isinstance(raw_tags, list):
                    continue
                tags = list(dict.fromkeys(tag.strip().casefold() for tag in raw_tags[:32]
                                          if isinstance(tag, str) and tag.strip() and len(tag.strip()) <= 32))
                if tags and total_tags + len(tags) <= 10000:
                    library_tags[style_id] = tags
                    total_tags += len(tags)
        safe["library_tags"] = library_tags

        for key, fallback in (("quick_switch_next_hotkey", "CTRL+ALT+UP"),
                              ("quick_switch_previous_hotkey", "CTRL+ALT+DOWN"),
                              ("quick_switch_favorite_hotkey", "CTRL+ALT+F")):
            value = safe.get(key)
            safe[key] = value.strip()[:128] if isinstance(value, str) and value.strip() else fallback

        return cls(**safe)
