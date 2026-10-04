from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ..core import AnimationManager
from ..crosshairs.models import CrosshairDefinition
from ..creator.models import CreatorCrosshair
from ..app_settings import BetaZoomSettings
from ..app_metadata import APP_VERSION
from .pages.about_page import AboutPage
from .pages.beta_page import BetaPage
from .pages.creator_page import CreatorPage
from .pages.crosshair_detail_page import CrosshairDetailPage
from .pages.crosshairs_page import CrosshairsPage
from .pages.export_page import ExportPage
from .pages.games_page import GameRowModel, GamesPage
from .pages.home_page import HomePage
from .pages.settings_page import SettingsPage
from .react_surface import ReactSurface
from .bridge_router import BridgeCommandRouter
from .sidebar import Sidebar


class MainWindow(QWidget):
    """Main application shell with animated sidebar and stacked pages."""

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
    import_game_requested = Signal(str)
    rescan_games_requested = Signal()
    beta_zoom_settings_changed = Signal(object)
    close_to_tray_requested = Signal()

    EXPANDED_WIDTH = 236
    COLLAPSED_WIDTH = 84

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
    ) -> None:
        super().__init__()
        self._definitions = definitions
        self._active_style_id = current_style_id
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
        self._beta_visible = beta_features_enabled
        self._sidebar_collapsed = bool(sidebar_collapsed)
        self._fullscreen_auto = False
        self._game_auto_switch = True
        self._games_data: list[GameRowModel] = []
        self._style_names: list[tuple[str, str]] = [(item.style_id, item.display_name) for item in definitions.values()]
        self._games_status = ""
        self._beta_monitors: list[tuple[str, str]] = []
        self._creator_model: dict | None = None
        self._web_page = "library"
        self._bridge_router = BridgeCommandRouter(self)
        style_names = [(item.style_id, item.display_name) for item in definitions.values()]
        self._home_page = HomePage(style_names=style_names, current_style_id=current_style_id)
        self._crosshairs_page = CrosshairsPage(
            definitions=definitions,
            current_style_id=current_style_id,
            selected_size_percent=selected_size_percent,
        )
        self._detail_page = CrosshairDetailPage()
        self._creator_page = CreatorPage()
        self._games_page = GamesPage()
        self._beta_page = BetaPage()
        self._settings_page = SettingsPage(
            theme_mode=theme_mode,
            accent_color=accent_color,
            global_size_percent=global_size_percent,
            storage_path=storage_path,
            beta_features_enabled=beta_features_enabled,
            auto_update_on_startup=auto_update_on_startup,
            run_on_startup_tray=run_on_startup_tray,
        )
        self._export_page = ExportPage()
        self._about_page = AboutPage()
        self._sidebar = Sidebar()
        self._stack = QStackedWidget(self)
        self._surface_stack = QStackedWidget(self)
        self._web_loaded = False
        self._web_selected_id = current_style_id
        self._web_revision = 0
        self._web_catalog_revision = 0
        self._animation_manager = AnimationManager(self)
        self._page_map: dict[str, QWidget] = {}
        self._current_page_id = "home"
        self._allow_close_once = False
        self._page_fade: QPropertyAnimation | None = None
        self._sidebar_animation = QPropertyAnimation(self._sidebar, b"minimumWidth", self)
        self._sidebar_animation.setDuration(240)
        self._sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._build_ui()
        self._wire_signals()
        self._apply_sidebar_state(sidebar_collapsed, animate=False)
        self.set_beta_page_visible(beta_features_enabled)
        self.set_beta_zoom_settings(beta_zoom_settings)
        self.navigate_to("home")

    def _build_ui(self) -> None:
        self.setWindowTitle("Crosshair Overlay")
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.svg"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1180, 780)
        self.setMinimumSize(980, 600)

        root = QHBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        shell = QFrame(self)
        shell.setObjectName("appShell")
        shell_layout = QHBoxLayout()
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(12)

        self._sidebar.setMinimumWidth(self.EXPANDED_WIDTH)
        self._sidebar.setMaximumWidth(self.EXPANDED_WIDTH)
        shell_layout.addWidget(self._sidebar, 0)

        content_surface = QFrame(self)
        content_surface.setObjectName("contentSurface")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._stack)
        self._web_index = -1
        self._surface_shortcut = QShortcut(QKeySequence("Ctrl+Shift+N"), self)
        self._surface_shortcut.activated.connect(self._toggle_surface)
        self._react_surface = ReactSurface(self)
        self._react_surface.command_requested.connect(self._on_react_command)
        self._react_surface.load_finished.connect(self._on_web_loaded)
        content_surface.setLayout(content_layout)
        shell_layout.addWidget(content_surface, 1)
        shell.setLayout(shell_layout)
        self._surface_stack.addWidget(shell)
        self._surface_stack.setCurrentIndex(0)
        self._web_index = self._surface_stack.addWidget(self._react_surface)
        root.addWidget(self._surface_stack)
        self.setLayout(root)

        self._page_map = {
            "home": self._home_page,
            "crosshairs": self._crosshairs_page,
            "my_crosshairs": self._crosshairs_page,
            "crosshair_detail": self._detail_page,
            "export": self._export_page,
            "about": self._about_page,
            "creator": self._creator_page,
            "games": self._games_page,
            "beta": self._beta_page,
            "settings": self._settings_page,
        }
        seen_pages: set[int] = set()
        for page in self._page_map.values():
            page_key = id(page)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            self._stack.addWidget(page)
        self._react_surface.start()

    def _wire_signals(self) -> None:
        self._sidebar.navigation_requested.connect(self.navigate_to)
        self._sidebar.collapse_toggled.connect(self.toggle_sidebar)
        self._sidebar.theme_mode_changed.connect(self.theme_mode_changed.emit)
        self._sidebar.quit_requested.connect(self.quit_requested.emit)

        self._home_page.enable_requested.connect(self.enable_overlay_requested.emit)
        self._home_page.disable_requested.connect(self.disable_overlay_requested.emit)
        self._home_page.quit_requested.connect(self.quit_requested.emit)
        self._home_page.quick_style_selected.connect(self.style_selected.emit)
        self._home_page.choose_crosshair_requested.connect(lambda: self.navigate_to("crosshairs"))

        self._crosshairs_page.style_selected.connect(self.style_selected.emit)
        self._crosshairs_page.detail_requested.connect(self._on_detail_requested)
        self._crosshairs_page.favorite_toggled.connect(self.style_favorite_toggled.emit)
        self._crosshairs_page.selected_size_changed.connect(self.selected_size_changed.emit)
        self._crosshairs_page.import_pack_requested.connect(self.import_pack_requested.emit)
        self._crosshairs_page.export_pack_requested.connect(self.style_export_requested.emit)
        self._crosshairs_page.export_selection_requested.connect(self.export_selection_requested.emit)
        self._export_page.export_requested.connect(self.export_pack_requested.emit)

        self._detail_page.back_requested.connect(self._return_from_detail)
        self._detail_page.activate_requested.connect(self.style_selected.emit)
        self._detail_page.live_style_changed.connect(self.style_live_updated.emit)
        self._detail_page.save_variant_requested.connect(self.style_variant_save_requested.emit)
        self._detail_page.export_requested.connect(self.style_export_requested.emit)
        self._detail_page.send_to_editor_requested.connect(self.send_to_editor_requested.emit)

        self._creator_page.save_requested.connect(self.creator_save_requested.emit)
        self._creator_page.export_requested.connect(self.creator_export_requested.emit)
        self._games_page.fullscreen_auto_toggled.connect(self.fullscreen_auto_toggled.emit)
        self._games_page.game_auto_switch_toggled.connect(self.game_auto_switch_toggled.emit)
        self._games_page.game_profile_updated.connect(self.game_profile_updated.emit)
        self._games_page.import_game_requested.connect(self.import_game_requested.emit)
        self._games_page.rescan_requested.connect(self.rescan_games_requested.emit)
        self._games_page.open_crosshair_library_requested.connect(lambda: self.navigate_to("crosshairs"))
        self._beta_page.settings_changed.connect(self.beta_zoom_settings_changed.emit)

        self._settings_page.accent_color_changed.connect(self.accent_color_changed.emit)
        self._settings_page.global_size_changed.connect(self.global_size_changed.emit)
        self._settings_page.storage_path_changed.connect(self.storage_path_changed.emit)
        self._settings_page.beta_features_changed.connect(self.beta_features_changed.emit)
        self._settings_page.auto_update_on_startup_changed.connect(self.auto_update_on_startup_changed.emit)
        self._settings_page.run_on_startup_tray_changed.connect(self.run_on_startup_tray_changed.emit)
        self._settings_page.reset_requested.connect(self.reset_requested.emit)
        self._settings_page.check_updates_requested.connect(self.check_updates_requested.emit)

        self._sidebar_animation.valueChanged.connect(self._on_sidebar_width_changed)

    def navigate_to(self, page_id: str) -> None:
        if self._surface_stack.currentIndex() != 0:
            self._surface_stack.setCurrentIndex(0)
        if page_id not in self._page_map:
            return
        if page_id == "my_crosshairs":
            self._crosshairs_page.set_quick_view("my")
        elif page_id == "crosshairs":
            self._crosshairs_page.set_quick_view("all")
        page = self._page_map[page_id]
        self._stack.setCurrentWidget(page)
        self._animate_current_page(page)
        self._current_page_id = page_id
        if page_id != "crosshair_detail":
            self._sidebar.set_selected(page_id)
        else:
            self._sidebar.set_selected(getattr(self, "_detail_return_page", "crosshairs"))

    def _on_detail_requested(self, style_id: str) -> None:
        self._detail_return_page = self._current_page_id if self._current_page_id in {"crosshairs", "my_crosshairs"} else "crosshairs"
        self.style_detail_requested.emit(style_id)
        self.navigate_to("crosshair_detail")

    def _return_from_detail(self) -> None:
        self.navigate_to(getattr(self, "_detail_return_page", "crosshairs"))

    def set_detail_definition(self, definition: CrosshairDefinition) -> None:
        self._detail_page.set_definition(definition)
        self._publish_web_state()

    def show_react_surface(self) -> bool:
        if self._web_index < 0:
            return False
        self._surface_stack.setCurrentIndex(self._web_index)
        self._set_web_lifecycle(active=self.isVisible())
        self._publish_web_state()
        return True

    def show_native_surface(self) -> None:
        self._surface_stack.setCurrentIndex(0)
        self._set_web_lifecycle(active=False)

    def _set_web_lifecycle(self, active: bool) -> None:
        if self._web_index < 0 or not self._web_loaded:
            return
        try:
            self._react_surface.set_active(active)
        except RuntimeError:
            pass

    def _toggle_surface(self) -> None:
        if self._web_index >= 0:
            if self._surface_stack.currentIndex() == self._web_index:
                self.show_native_surface()
            else:
                self.show_react_surface()

    def _on_web_loaded(self, ok: bool) -> None:
        if ok:
            self._web_loaded = True
            self.show_react_surface()
        else:
            self.show_native_surface()

    def _web_snapshot(self) -> dict:
        self._web_revision += 1
        visible_styles = list(self._definitions.values())[:48]
        visible_ids = {item.style_id for item in visible_styles}
        for style_id in (self._web_selected_id, self._active_style_id):
            if style_id in self._definitions and style_id not in visible_ids:
                visible_styles.append(self._definitions[style_id])
                visible_ids.add(style_id)
        return {"version": 1, "revision": self._web_revision, "theme": self._theme_mode, "resolvedTheme": self._resolved_theme, "accent": self._accent_color, "appVersion": APP_VERSION, "runtime": "native",
                "overlay": self._overlay_status, "activeId": self._active_style_id,
                "selectedId": self._web_selected_id, "page": self._web_page,
                "styleCount": len(self._definitions), "catalogRevision": self._web_catalog_revision,
                "styles": [self._style_payload(item) for item in visible_styles],
                "settings": {"selectedSize": self._selected_size, "globalSize": self._global_size,
                             "theme": self._theme_mode, "accent": self._accent_color,
                             "autoUpdate": self._auto_update_on_startup, "startupTray": self._run_on_startup_tray,
                             "fullscreenAuto": self._fullscreen_auto, "gameAutoSwitch": self._game_auto_switch,
                             "storagePath": self._storage_path, "betaVisible": self._beta_visible,
                             "sidebarCollapsed": self._sidebar_collapsed,
                             "zoom": self._zoom_payload(), "monitors": [{"id": mid, "name": name} for mid, name in self._beta_monitors]},
                "games": [{"id": g.game_id, "title": g.title, "source": g.source, "executablePath": g.executable_path,
                           "iconPath": g.icon_path, "styleId": g.assigned_style_id, "enabled": g.enabled} for g in self._games_data],
                "gamesStatus": self._games_status, "creator": self._creator_model}

    def _zoom_payload(self) -> dict:
        s = self._beta_zoom_settings
        return {"sidebarEnabled": s.sidebar_enabled, "liveEnabled": s.live_enabled, "zoomEnabled": s.zoom_enabled,
                "hotkeySequence": s.hotkey_sequence, "displayMode": s.display_mode, "targetMonitorId": s.target_monitor_id,
                "positionXPercent": s.position_x_percent, "positionYPercent": s.position_y_percent,
                "zoomPercent": s.zoom_percent, "animationEnabled": s.animation_enabled, "animationDurationMs": s.animation_duration_ms}

    def _style_payload(self, item: CrosshairDefinition) -> dict:
        s = item.style
        rgba = getattr(s, "color_rgba", (255, 255, 255, 255))
        outline_rgba = getattr(s, "outline_rgba", (0, 0, 0, 220))
        return {"id": item.style_id, "name": item.display_name, "family": item.family,
                "source": item.source_type, "tags": list(item.tags), "favorite": item.is_favorite,
                "color": "#%02x%02x%02x" % tuple(rgba[:3]), "opacity": int(rgba[3]) if len(rgba) > 3 else 255,
                "shape": str(getattr(s.shape, "value", s.shape)), "dot": bool(s.center_dot),
                "active": item.style_id == self._active_style_id, "armLength": s.arm_length,
                "gap": s.gap, "thickness": s.thickness, "circleRadius": s.circle_radius,
                "circleThickness": s.circle_thickness, "centerDotSize": s.center_dot_size,
                "tStyle": s.t_style, "rotationDegrees": s.rotation_degrees,
                "outlineEnabled": s.outline_enabled, "outlineThickness": s.outline_thickness,
                "outlineColor": "#%02x%02x%02x" % tuple(outline_rgba[:3]),
                "outlineOpacity": int(outline_rgba[3]) if len(outline_rgba) > 3 else 255,
                "customGridSize": s.custom_grid_size, "customCellSize": s.custom_cell_size,
                "customFilledCells": [[x, y] for x, y in s.custom_filled_cells],
                "canvasSize": s.canvas_size, "description": item.description,
                "editableSettings": [self._editable_payload(item, spec.key, spec.label, spec.kind.value, spec.minimum, spec.maximum, spec.step) for spec in item.editable_settings]}

    @staticmethod
    def _editable_payload(item: CrosshairDefinition, key: str, label: str, kind: str, minimum, maximum, step) -> dict:
        if key == "color_rgba":
            value = "#{:02X}{:02X}{:02X}".format(*item.style.color_rgba[:3])
        elif key == "opacity":
            value = item.style.color_rgba[3]
        elif hasattr(item.style, key):
            value = getattr(item.style, key)
        else:
            value = None
        return {"key": key, "label": label, "kind": kind, "minimum": minimum, "maximum": maximum, "step": step, "value": value}

    def _publish_web_event(self, snapshot: dict | None = None) -> None:
        self._react_surface.publish(snapshot or self._publish_web_state())

    def _on_react_command(self, command: str, payload: object, request_id: str) -> None:
        try:
            if not isinstance(payload, dict):
                raise ValueError("Command payload must be an object")
            result = self._bridge_router.dispatch(command, payload)
            self._react_surface.complete(request_id, result)
        except Exception as exc:
            self._react_surface.complete(request_id, error=str(exc))

    def _publish_web_state(self) -> dict:
        return self._web_snapshot()

    def _update_web_definitions(self, definitions: "OrderedDict[str, CrosshairDefinition]") -> None:
        self._definitions = definitions
        self._web_catalog_revision += 1
        self._publish_web_event()

    def toggle_sidebar(self) -> None:
        self._apply_sidebar_state(not self._sidebar.collapsed, animate=True)

    def _apply_sidebar_state(self, collapsed: bool, animate: bool) -> None:
        self._sidebar_collapsed = collapsed
        self._sidebar.set_collapsed(collapsed)
        target_width = self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH
        if animate:
            self._sidebar_animation.stop()
            self._sidebar_animation.setStartValue(self._sidebar.width())
            self._sidebar_animation.setEndValue(target_width)
            self._sidebar_animation.start()
        else:
            self._sidebar.setMinimumWidth(target_width)
            self._sidebar.setMaximumWidth(target_width)
        self.sidebar_collapsed_changed.emit(collapsed)

    def _on_sidebar_width_changed(self, value: int) -> None:
        width = int(value)
        self._sidebar.setMinimumWidth(width)
        self._sidebar.setMaximumWidth(width)

    def _animate_current_page(self, page: QWidget) -> None:
        if self._page_fade is not None:
            self._page_fade.stop()
        effect = page.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
        self._page_fade = self._animation_manager.fade_in(page)

    def refresh_definitions(self, definitions: "OrderedDict[str, CrosshairDefinition]", selected_style_id: str, catalog_changed: bool = True) -> None:
        self._definitions = definitions
        if catalog_changed:
            self._web_catalog_revision += 1
        if self._web_selected_id not in definitions:
            self._web_selected_id = selected_style_id
        style_names = [(item.style_id, item.display_name) for item in definitions.values()]
        self._home_page.refresh_styles(style_names=style_names, selected_style_id=selected_style_id)
        self._crosshairs_page.refresh_definitions(definitions=definitions, selected_style_id=selected_style_id)
        self._publish_web_event()

    def set_overlay_status(self, enabled: bool) -> None:
        self._overlay_status = bool(enabled)
        self._home_page.set_overlay_status(enabled)
        self._publish_web_event()

    def set_selected_style(self, style_id: str) -> None:
        self._active_style_id = style_id
        self._home_page.set_selected_style(style_id)
        self._crosshairs_page.set_selected_style(style_id)
        self._publish_web_event()

    def set_selected_style_name(self, style_name: str) -> None:
        self._home_page.set_selected_style_name(style_name)

    def set_active_style_preview(self, definition: CrosshairDefinition) -> None:
        self._home_page.set_active_style_preview(definition.style)
        self._export_page.set_definition(definition)

    def set_selected_size(self, value: int) -> None:
        self._selected_size = value
        self._crosshairs_page.set_selected_size(value)
        self._publish_web_event()

    def set_theme_values(self, theme_mode: str, accent_color: str, resolved_theme: str | None = None) -> None:
        self._theme_mode = theme_mode
        if resolved_theme in {"dark", "light"}:
            self._resolved_theme = resolved_theme
        self._accent_color = accent_color
        self._sidebar.set_theme_mode(theme_mode)
        self._settings_page.set_theme(theme_mode=theme_mode, accent_color=accent_color)
        self._crosshairs_page.set_accent_color(accent_color)
        self._publish_web_event()

    def set_global_size(self, value: int) -> None:
        self._global_size = value
        self._settings_page.set_global_size(value)
        self._publish_web_event()

    def set_storage_path(self, path: str) -> None:
        self._storage_path = path
        self._settings_page.set_storage_path(path)
        self._publish_web_event()

    def open_creator_with_model(self, model: CreatorCrosshair) -> None:
        self._creator_page.load_from_model(model)
        self._creator_model = model.to_dict()
        if self._surface_stack.currentIndex() == self._web_index:
            self._web_page = "creator"
            self._publish_web_event()
            return
        self._publish_web_event()
        self.navigate_to("creator")

    def set_games_data(self, games: list[GameRowModel], style_items: list[tuple[str, str]]) -> None:
        self._games_data = list(games)
        self._style_names = list(style_items)
        self._games_page.set_games(games=games, style_items=style_items)
        self._publish_web_event()

    def set_games_toggles(self, fullscreen_enabled: bool, game_switch_enabled: bool) -> None:
        self._fullscreen_auto = bool(fullscreen_enabled)
        self._game_auto_switch = bool(game_switch_enabled)
        self._games_page.set_runtime_toggles(
            fullscreen_enabled=fullscreen_enabled,
            game_switch_enabled=game_switch_enabled,
        )
        self._publish_web_event()

    def set_games_status(self, text: str) -> None:
        self._games_status = text
        self._games_page.set_runtime_status(text)
        self._publish_web_event()

    def set_beta_page_visible(self, visible: bool) -> None:
        self._beta_visible = bool(visible)
        self._settings_page.set_beta_features_enabled(visible)
        self._sidebar.set_beta_visible(visible)
        if not visible and self._current_page_id == "beta":
            self.navigate_to("home")
        self._publish_web_event()

    def set_startup_preferences(self, auto_update_on_startup: bool, run_on_startup_tray: bool) -> None:
        self._auto_update_on_startup = bool(auto_update_on_startup)
        self._run_on_startup_tray = bool(run_on_startup_tray)
        self._settings_page.set_startup_preferences(
            auto_update_on_startup=auto_update_on_startup,
            run_on_startup_tray=run_on_startup_tray,
        )
        self._publish_web_event()

    def set_update_available(self, available: bool) -> None:
        self._sidebar.set_update_alert(bool(available))

    def set_beta_zoom_settings(self, settings: BetaZoomSettings) -> None:
        self._beta_zoom_settings = settings
        self._beta_page.set_settings(settings)
        self._publish_web_event()

    def set_beta_monitor_choices(self, choices: list[tuple[str, str]]) -> None:
        self._beta_monitors = list(choices)
        self._beta_page.set_monitor_choices(choices)
        self._publish_web_event()

    def set_beta_preview(self, pixmap) -> None:
        self._beta_page.set_preview_pixmap(pixmap)

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
        self._set_web_lifecycle(active=self._surface_stack.currentIndex() == self._web_index)

    def allow_close_once(self) -> None:
        self._allow_close_once = True


