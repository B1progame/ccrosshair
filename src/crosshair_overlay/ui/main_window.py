from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..app_metadata import APP_VERSION
from ..app_settings import AccessibilitySettings, BetaZoomSettings, ReactiveSettings
from ..creator.models import CreatorCrosshair
from ..crosshairs.models import CrosshairDefinition
from .bridge_router import BridgeCommandRouter
from .react_surface import ReactSurface


class MainWindow(QWidget):
    """Single-surface React window backed by the native application services."""

    enable_overlay_requested = Signal()
    disable_overlay_requested = Signal()
    quit_requested = Signal()
    style_selected = Signal(str)
    style_detail_requested = Signal(str)
    style_favorite_toggled = Signal(str)
    style_live_updated = Signal(object)
    style_variant_save_requested = Signal(object)
    style_export_requested = Signal(str, str)
    selected_size_changed = Signal(int)
    theme_mode_changed = Signal(str)
    accent_color_changed = Signal(str)
    global_size_changed = Signal(int)
    storage_path_changed = Signal(str)
    beta_features_changed = Signal(bool)
    auto_update_on_startup_changed = Signal(bool)
    run_on_startup_tray_changed = Signal(bool)
    reset_requested = Signal()
    check_updates_requested = Signal()
    import_pack_requested = Signal(str)
    export_pack_requested = Signal(str)
    creator_save_requested = Signal(object, bool)
    creator_export_requested = Signal(object, str)
    send_to_editor_requested = Signal(str)
    export_selection_requested = Signal(list, str)
    sidebar_collapsed_changed = Signal(bool)
    fullscreen_auto_toggled = Signal(bool)
    game_auto_switch_toggled = Signal(bool)
    game_profile_updated = Signal(str, str, bool)
    game_loadouts_updated = Signal(str, object, str)
    game_loadout_selected = Signal(str, str)
    import_game_requested = Signal(str)
    rescan_games_requested = Signal()
    beta_zoom_settings_changed = Signal(object)
    accessibility_changed = Signal(object)
    reactive_settings_changed = Signal(object)
    loadout_hotkeys_changed = Signal(str, str, str)
    monitor_offset_changed = Signal(str, int, int)
    library_metadata_changed = Signal(object, object)
    close_to_tray_requested = Signal()

    _PAGE_ALIASES = {
        "home": "home", "crosshairs": "library", "library": "library",
        "my_crosshairs": "my_crosshairs", "crosshair_detail": "detail", "detail": "detail",
        "export": "export", "about": "about", "creator": "creator", "games": "games",
        "beta": "zoom", "zoom": "zoom", "settings": "settings",
        "compatibility": "compatibility",
    }

    def __init__(
        self,
        definitions: "OrderedDict[str, CrosshairDefinition]",
        current_style_id: str,
        selected_size_percent: int,
        theme_mode: str,
        accent_color: str,
        global_size_percent: int,
        storage_path: str,
        beta_features_enabled: bool,
        auto_update_on_startup: bool,
        run_on_startup_tray: bool,
        beta_zoom_settings: BetaZoomSettings,
        sidebar_collapsed: bool,
        accessibility_settings: AccessibilitySettings,
        reactive_settings: ReactiveSettings,
        recent_style_ids: list[str],
        recent_crosshair_colors: list[str],
    ) -> None:
        super().__init__()
        self._definitions = definitions
        self._active_style_id = current_style_id
        self._web_selected_id = current_style_id
        self._overlay_status = False
        self._theme_mode = theme_mode
        self._resolved_theme = theme_mode if theme_mode in {"dark", "light"} else "dark"
        self._accent_color = accent_color
        self._storage_path = storage_path
        self._selected_size = selected_size_percent
        self._global_size = global_size_percent
        self._auto_update_on_startup = auto_update_on_startup
        self._run_on_startup_tray = run_on_startup_tray
        self._beta_zoom_settings = beta_zoom_settings
        self._accessibility_settings = accessibility_settings
        self._reactive_settings = reactive_settings
        self._recent_style_ids = recent_style_ids
        self._recent_crosshair_colors = recent_crosshair_colors
        self._quick_switch_next_hotkey = "CTRL+ALT+UP"
        self._quick_switch_previous_hotkey = "CTRL+ALT+DOWN"
        self._quick_switch_favorite_hotkey = "CTRL+ALT+F"
        self._monitor_offsets: dict[str, dict[str, int]] = {}
        self._library_collections: list[dict] = []
        self._library_tags: dict[str, list[str]] = {}
        self._zoom_diagnostics: dict[str, object] = {}
        self._beta_visible = beta_features_enabled
        self._sidebar_collapsed = bool(sidebar_collapsed)
        self._fullscreen_auto = False
        self._game_auto_switch = True
        self._games_data: list[object] = []
        self._games_status = ""
        self._beta_monitors: list[tuple[str, str]] = []
        self._creator_model: dict | None = None
        self.creator_save_handler = None
        self.keyboard_entry_active = False
        self._web_page = "home"
        self._current_page_id = "home"
        self._web_revision = 0
        self._web_catalog_revision = 0
        self._web_loaded = False
        self._update_available = False
        self._allow_close_once = False
        self._bridge_router = BridgeCommandRouter(self)

        self.setWindowTitle("Crosshair Overlay")
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1180, 780)
        self.setMinimumSize(980, 600)

        self._react_surface = ReactSurface(self)
        self._react_surface.command_requested.connect(self._on_react_command)
        self._react_surface.load_finished.connect(self._on_web_loaded)
        self._load_error = QLabel(self)
        self._load_error.setWordWrap(True)
        self._load_error.setVisible(False)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._react_surface, 1)
        layout.addWidget(self._load_error)
        self.setLayout(layout)
        self._react_surface.start()

    def navigate_to(self, page_id: str) -> None:
        page = self._PAGE_ALIASES.get(page_id)
        if page is None:
            return
        self._web_page = page
        self._current_page_id = page
        self._publish_web_event()

    def show_react_surface(self) -> bool:
        self._set_web_lifecycle(active=self.isVisible())
        return True

    def _set_web_lifecycle(self, active: bool) -> None:
        if not self._web_loaded:
            return
        try:
            self._react_surface.set_active(active)
        except RuntimeError:
            pass

    def _on_web_loaded(self, ok: bool) -> None:
        self._web_loaded = bool(ok)
        self._load_error.setVisible(not ok)
        if not ok:
            self._load_error.setText("The React control interface could not load. Rebuild the application bundle and restart Crosshair Overlay.")
            return
        self._publish_web_event()
        self._set_web_lifecycle(active=self.isVisible())

    def _web_snapshot(self) -> dict:
        self._web_revision += 1
        visible_styles = list(self._definitions.values())[:48]
        visible_ids = {item.style_id for item in visible_styles}
        for style_id in (self._web_selected_id, self._active_style_id):
            if style_id in self._definitions and style_id not in visible_ids:
                visible_styles.append(self._definitions[style_id])
                visible_ids.add(style_id)
        return {
            "version": 1,
            "revision": self._web_revision,
            "theme": self._theme_mode,
            "resolvedTheme": self._resolved_theme,
            "accent": self._accent_color,
            "appVersion": APP_VERSION,
            "runtime": "native",
            "overlay": self._overlay_status,
            "activeId": self._active_style_id,
            "selectedId": self._web_selected_id,
            "page": self._web_page,
            "styleCount": len(self._definitions),
            "catalogRevision": self._web_catalog_revision,
            "styles": [self._style_payload(item) for item in visible_styles],
            "settings": {
                "selectedSize": self._selected_size,
                "globalSize": self._global_size,
                "theme": self._theme_mode,
                "accent": self._accent_color,
                "autoUpdate": self._auto_update_on_startup,
                "startupTray": self._run_on_startup_tray,
                "fullscreenAuto": self._fullscreen_auto,
                "gameAutoSwitch": self._game_auto_switch,
                "storagePath": self._storage_path,
                "betaVisible": self._beta_visible,
                "sidebarCollapsed": self._sidebar_collapsed,
                "zoom": self._zoom_payload(),
                "accessibility": {
                    "highContrast": self._accessibility_settings.high_contrast,
                    "reducedMotion": self._accessibility_settings.reduced_motion,
                    "density": self._accessibility_settings.density,
                    "textScale": self._accessibility_settings.text_scale,
                },
                "reactive": {
                    "enabled": self._reactive_settings.enabled,
                    "firePulse": self._reactive_settings.fire_pulse,
                    "gapExpansion": self._reactive_settings.gap_expansion,
                    "opacityPulse": self._reactive_settings.opacity_pulse,
                    "hideOnAds": self._reactive_settings.hide_on_ads,
                    "emergencyHotkey": self._reactive_settings.emergency_hotkey,
                    "fireDurationMs": self._reactive_settings.fire_duration_ms,
                    "fireAmplitudePercent": self._reactive_settings.fire_amplitude_percent,
                    "adsTransitionMs": self._reactive_settings.ads_transition_ms,
                    "adsMode": self._reactive_settings.ads_mode,
                },
                "recentStyleIds": list(self._recent_style_ids),
                "recentCrosshairColors": list(self._recent_crosshair_colors),
                "monitorOffsets": dict(self._monitor_offsets),
                "libraryCollections": [dict(item) for item in self._library_collections],
                "libraryTags": {key: list(value) for key, value in self._library_tags.items()},
                "quickSwitchNextHotkey": self._quick_switch_next_hotkey,
                "quickSwitchPreviousHotkey": self._quick_switch_previous_hotkey,
                "quickSwitchFavoriteHotkey": self._quick_switch_favorite_hotkey,
                "zoomDiagnostics": dict(self._zoom_diagnostics),
                "monitors": [{"id": mid, "name": name} for mid, name in self._beta_monitors],
            },
            "games": [
                {
                    "id": game.game_id,
                    "title": game.title,
                    "source": game.source,
                    "executablePath": game.executable_path,
                    "iconPath": game.icon_path,
                    "styleId": game.assigned_style_id,
                    "enabled": game.enabled,
                    "loadouts": list(game.loadouts),
                    "activeLoadoutId": game.active_loadout_id,
                }
                for game in self._games_data
            ],
            "gamesStatus": self._games_status,
            "creator": self._creator_model,
            "updateAvailable": self._update_available,
        }

    def _zoom_payload(self) -> dict:
        settings = self._beta_zoom_settings
        return {
            "sidebarEnabled": settings.sidebar_enabled,
            "liveEnabled": settings.live_enabled,
            "zoomEnabled": settings.zoom_enabled,
            "hotkeySequence": settings.hotkey_sequence,
            "displayMode": settings.display_mode,
            "targetMonitorId": settings.target_monitor_id,
            "positionXPercent": settings.position_x_percent,
            "positionYPercent": settings.position_y_percent,
            "zoomPercent": settings.zoom_percent,
            "runtimeMode": settings.runtime_mode,
            "autoAdaptEnabled": settings.auto_adapt_enabled,
            "zoomInHotkeySequence": settings.zoom_in_hotkey_sequence,
            "zoomOutHotkeySequence": settings.zoom_out_hotkey_sequence,
            "zoomResetHotkeySequence": settings.zoom_reset_hotkey_sequence,
            "animationEnabled": settings.animation_enabled,
            "animationDurationMs": settings.animation_duration_ms,
            "consumeMouseWheel": settings.consume_mouse_wheel,
            "cleanupEnabled": settings.cleanup_enabled,
            "cleanupRadius": settings.cleanup_radius,
            "cleanupStrength": settings.cleanup_strength,
            "cleanupPreview": settings.cleanup_preview,
            "hideCrosshairWhenZoomed": settings.hide_crosshair_when_zoomed,
        }

    def _style_payload(self, item: CrosshairDefinition) -> dict:
        style = item.style
        rgba = getattr(style, "color_rgba", (255, 255, 255, 255))
        outline_rgba = getattr(style, "outline_rgba", (0, 0, 0, 220))
        return {
            "id": item.style_id,
            "name": item.display_name,
            "family": item.family,
            "source": item.source_type,
            "tags": list(dict.fromkeys((*item.tags, *self._library_tags.get(item.style_id, [])))),
            "favorite": item.is_favorite,
            "color": "#%02x%02x%02x" % tuple(rgba[:3]),
            "opacity": int(rgba[3]) if len(rgba) > 3 else 255,
            "shape": str(getattr(style.shape, "value", style.shape)),
            "dot": bool(style.center_dot),
            "active": item.style_id == self._active_style_id,
            "armLength": style.arm_length,
            "gap": style.gap,
            "thickness": style.thickness,
            "circleRadius": style.circle_radius,
            "circleThickness": style.circle_thickness,
            "centerDotSize": style.center_dot_size,
            "tStyle": style.t_style,
            "rotationDegrees": style.rotation_degrees,
            "outlineEnabled": style.outline_enabled,
            "outlineThickness": style.outline_thickness,
            "outlineColor": "#%02x%02x%02x" % tuple(outline_rgba[:3]),
            "outlineOpacity": int(outline_rgba[3]) if len(outline_rgba) > 3 else 255,
            "customGridSize": style.custom_grid_size,
            "customCellSize": style.custom_cell_size,
            "customFilledCells": [[x, y] for x, y in style.custom_filled_cells],
            "canvasSize": style.canvas_size,
            "description": item.description,
            "aliases": list(item.aliases),
            "originGame": item.origin_game,
            "author": item.author,
            "sourceUrl": item.source_url,
            "reuseStatus": item.reuse_status,
            "approximate": item.approximate,
            "catalogVersion": item.catalog_version,
            "editableSettings": [
                self._editable_payload(item, spec.key, spec.label, spec.kind.value, spec.minimum, spec.maximum, spec.step)
                for spec in item.editable_settings
            ],
        }

    @staticmethod
    def _editable_payload(item: CrosshairDefinition, key: str, label: str, kind: str, minimum, maximum, step) -> dict:
        if key == "color_rgba":
            value = "#{:02X}{:02X}{:02X}".format(*item.style.color_rgba[:3])
        elif key == "outline_rgba":
            value = "#{:02X}{:02X}{:02X}".format(*item.style.outline_rgba[:3])
        elif key == "opacity":
            value = item.style.color_rgba[3]
        elif hasattr(item.style, key):
            value = getattr(item.style, key)
        else:
            value = None
        return {"key": key, "label": label, "kind": kind, "minimum": minimum, "maximum": maximum, "step": step, "value": value}

    def _publish_web_event(self, snapshot: dict | None = None) -> None:
        if self._web_loaded:
            self._react_surface.publish(snapshot or self._publish_web_state())

    def _publish_web_state(self) -> dict:
        return self._web_snapshot()

    def _on_react_command(self, command: str, payload: object, request_id: str) -> None:
        try:
            if not isinstance(payload, dict):
                raise ValueError("Command payload must be an object")
            result = self._bridge_router.dispatch(command, payload)
            self._react_surface.complete(request_id, result)
        except Exception as exc:
            self._react_surface.complete(request_id, error=str(exc))

    def refresh_definitions(self, definitions: "OrderedDict[str, CrosshairDefinition]", selected_style_id: str, catalog_changed: bool = True) -> None:
        self._definitions = definitions
        if self._web_selected_id not in definitions:
            self._web_selected_id = selected_style_id
        if catalog_changed:
            self._web_catalog_revision += 1
        self._publish_web_event()

    def set_overlay_status(self, enabled: bool) -> None:
        self._overlay_status = bool(enabled)
        self._publish_web_event()

    def set_selected_style(self, style_id: str) -> None:
        self._active_style_id = style_id
        self._publish_web_event()

    def set_selected_style_name(self, style_name: str) -> None:
        del style_name

    def set_active_style_preview(self, definition: CrosshairDefinition) -> None:
        del definition

    def set_detail_definition(self, definition: CrosshairDefinition) -> None:
        del definition
        self._publish_web_event()

    def set_selected_size(self, value: int) -> None:
        self._selected_size = value
        self._publish_web_event()

    def set_theme_values(self, theme_mode: str, accent_color: str, resolved_theme: str | None = None) -> None:
        self._theme_mode = theme_mode
        if resolved_theme in {"dark", "light"}:
            self._resolved_theme = resolved_theme
        self._accent_color = accent_color
        self._publish_web_event()

    def set_global_size(self, value: int) -> None:
        self._global_size = value
        self._publish_web_event()

    def set_storage_path(self, path: str) -> None:
        self._storage_path = path
        self._publish_web_event()

    def open_creator_with_model(self, model: CreatorCrosshair) -> None:
        self._creator_model = model.to_dict()
        self.navigate_to("creator")

    def set_creator_model(self, model: CreatorCrosshair) -> None:
        self._creator_model = model.to_dict()
        self._publish_web_event()

    def set_games_data(self, games: list[object], style_items: list[tuple[str, str]]) -> None:
        del style_items
        self._games_data = list(games)
        self._publish_web_event()

    def set_games_toggles(self, fullscreen_enabled: bool, game_switch_enabled: bool) -> None:
        self._fullscreen_auto = bool(fullscreen_enabled)
        self._game_auto_switch = bool(game_switch_enabled)
        self._publish_web_event()

    def set_games_status(self, text: str) -> None:
        self._games_status = text
        self._publish_web_event()

    def set_beta_page_visible(self, visible: bool) -> None:
        self._beta_visible = bool(visible)
        if not visible and self._current_page_id == "zoom":
            self.navigate_to("home")
        else:
            self._publish_web_event()

    def set_startup_preferences(self, auto_update_on_startup: bool, run_on_startup_tray: bool) -> None:
        self._auto_update_on_startup = bool(auto_update_on_startup)
        self._run_on_startup_tray = bool(run_on_startup_tray)
        self._publish_web_event()

    def set_update_available(self, available: bool) -> None:
        self._update_available = bool(available)
        self._publish_web_event()

    def set_beta_zoom_settings(self, settings: BetaZoomSettings) -> None:
        self._beta_zoom_settings = settings
        self._publish_web_event()

    def set_accessibility_settings(self, settings: AccessibilitySettings) -> None:
        self._accessibility_settings = settings
        self._publish_web_event()

    def set_reactive_settings(self, settings: ReactiveSettings) -> None:
        self._reactive_settings = settings
        self._publish_web_event()

    def set_quick_switch_hotkeys(self, next_hotkey: str, previous_hotkey: str, favorite_hotkey: str) -> None:
        self._quick_switch_next_hotkey = next_hotkey
        self._quick_switch_previous_hotkey = previous_hotkey
        self._quick_switch_favorite_hotkey = favorite_hotkey
        self._publish_web_event()

    def set_monitor_offsets(self, offsets: dict[str, dict[str, int]]) -> None:
        self._monitor_offsets = {key: dict(value) for key, value in offsets.items()}
        self._publish_web_event()

    def set_library_metadata(self, collections: list[dict], tags: dict[str, list[str]]) -> None:
        self._library_collections = [dict(item) for item in collections]
        self._library_tags = {key: list(value) for key, value in tags.items()}
        self._web_catalog_revision += 1
        self._publish_web_event()

    def set_recent_style_ids(self, style_ids: list[str]) -> None:
        self._recent_style_ids = list(style_ids)
        self._publish_web_event()

    def set_recent_crosshair_colors(self, colors: list[str]) -> None:
        self._recent_crosshair_colors = list(colors)
        self._publish_web_event()

    def set_zoom_diagnostics(self, diagnostics: dict[str, object]) -> None:
        self._zoom_diagnostics = dict(diagnostics)
        self._publish_web_event()

    def set_beta_monitor_choices(self, choices: list[tuple[str, str]]) -> None:
        self._beta_monitors = list(choices)
        self._publish_web_event()

    @property
    def current_page_id(self) -> str:
        return self._current_page_id

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._allow_close_once:
            event.accept()
            return
        self.close_to_tray_requested.emit()
        event.ignore()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._set_web_lifecycle(active=False)
        super().hideEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._set_web_lifecycle(active=True)

    def allow_close_once(self) -> None:
        self._allow_close_once = True
