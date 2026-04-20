from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from ..crosshairs.models import CrosshairDefinition
from ..creator.models import CreatorCrosshair
from ..app_settings import BetaZoomSettings
from .pages.beta_page import BetaPage
from .pages.creator_page import CreatorPage
from .pages.crosshair_detail_page import CrosshairDetailPage
from .pages.crosshairs_page import CrosshairsPage
from .pages.games_page import GameRowModel, GamesPage
from .pages.home_page import HomePage
from .pages.settings_page import SettingsPage
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

    EXPANDED_WIDTH = 218
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
        beta_zoom_settings: BetaZoomSettings,
        sidebar_collapsed: bool,
    ) -> None:
        super().__init__()
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
        )
        self._sidebar = Sidebar()
        self._stack = QStackedWidget(self)
        self._page_map: dict[str, QWidget] = {}
        self._current_page_id = "home"
        self._allow_close_once = False
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
        self.resize(1120, 700)
        self.setMinimumSize(940, 560)

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
        content_surface.setLayout(content_layout)
        shell_layout.addWidget(content_surface, 1)
        shell.setLayout(shell_layout)

        root.addWidget(shell)
        self.setLayout(root)

        self._page_map = {
            "home": self._home_page,
            "crosshairs": self._crosshairs_page,
            "crosshair_detail": self._detail_page,
            "creator": self._creator_page,
            "games": self._games_page,
            "beta": self._beta_page,
            "settings": self._settings_page,
        }
        for page in self._page_map.values():
            self._stack.addWidget(page)

    def _wire_signals(self) -> None:
        self._sidebar.navigation_requested.connect(self.navigate_to)
        self._sidebar.collapse_toggled.connect(self.toggle_sidebar)

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
        self._crosshairs_page.export_pack_requested.connect(self.export_pack_requested.emit)
        self._crosshairs_page.export_selection_requested.connect(self.export_selection_requested.emit)

        self._detail_page.back_requested.connect(lambda: self.navigate_to("crosshairs"))
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

        self._settings_page.theme_mode_changed.connect(self.theme_mode_changed.emit)
        self._settings_page.accent_color_changed.connect(self.accent_color_changed.emit)
        self._settings_page.global_size_changed.connect(self.global_size_changed.emit)
        self._settings_page.storage_path_changed.connect(self.storage_path_changed.emit)
        self._settings_page.beta_features_changed.connect(self.beta_features_changed.emit)
        self._settings_page.reset_requested.connect(self.reset_requested.emit)
        self._settings_page.check_updates_requested.connect(self.check_updates_requested.emit)

        self._sidebar_animation.valueChanged.connect(self._on_sidebar_width_changed)

    def navigate_to(self, page_id: str) -> None:
        if page_id not in self._page_map:
            return
        page = self._page_map[page_id]
        self._stack.setCurrentWidget(page)
        self._current_page_id = page_id
        if page_id != "crosshair_detail":
            self._sidebar.set_selected(page_id)
        else:
            self._sidebar.set_selected("crosshairs")

    def _on_detail_requested(self, style_id: str) -> None:
        self.style_detail_requested.emit(style_id)
        self.navigate_to("crosshair_detail")

    def set_detail_definition(self, definition: CrosshairDefinition) -> None:
        self._detail_page.set_definition(definition)

    def toggle_sidebar(self) -> None:
        self._apply_sidebar_state(not self._sidebar.collapsed, animate=True)

    def _apply_sidebar_state(self, collapsed: bool, animate: bool) -> None:
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

    def refresh_definitions(self, definitions: "OrderedDict[str, CrosshairDefinition]", selected_style_id: str) -> None:
        style_names = [(item.style_id, item.display_name) for item in definitions.values()]
        self._home_page.refresh_styles(style_names=style_names, selected_style_id=selected_style_id)
        self._crosshairs_page.refresh_definitions(definitions=definitions, selected_style_id=selected_style_id)

    def set_overlay_status(self, enabled: bool) -> None:
        self._home_page.set_overlay_status(enabled)

    def set_selected_style(self, style_id: str) -> None:
        self._home_page.set_selected_style(style_id)
        self._crosshairs_page.set_selected_style(style_id)

    def set_selected_style_name(self, style_name: str) -> None:
        self._home_page.set_selected_style_name(style_name)

    def set_active_style_preview(self, definition: CrosshairDefinition) -> None:
        self._home_page.set_active_style_preview(definition.style)

    def set_selected_size(self, value: int) -> None:
        self._crosshairs_page.set_selected_size(value)

    def set_theme_values(self, theme_mode: str, accent_color: str) -> None:
        self._settings_page.set_theme(theme_mode=theme_mode, accent_color=accent_color)

    def set_global_size(self, value: int) -> None:
        self._settings_page.set_global_size(value)

    def set_storage_path(self, path: str) -> None:
        self._settings_page.set_storage_path(path)

    def open_creator_with_model(self, model: CreatorCrosshair) -> None:
        self._creator_page.load_from_model(model)
        self.navigate_to("creator")

    def set_games_data(self, games: list[GameRowModel], style_items: list[tuple[str, str]]) -> None:
        self._games_page.set_games(games=games, style_items=style_items)

    def set_games_toggles(self, fullscreen_enabled: bool, game_switch_enabled: bool) -> None:
        self._games_page.set_runtime_toggles(
            fullscreen_enabled=fullscreen_enabled,
            game_switch_enabled=game_switch_enabled,
        )

    def set_games_status(self, text: str) -> None:
        self._games_page.set_runtime_status(text)

    def set_beta_page_visible(self, visible: bool) -> None:
        self._settings_page.set_beta_features_enabled(visible)
        self._sidebar.set_beta_visible(visible)
        if not visible and self._current_page_id == "beta":
            self.navigate_to("home")

    def set_beta_zoom_settings(self, settings: BetaZoomSettings) -> None:
        self._beta_page.set_settings(settings)

    def set_beta_monitor_choices(self, choices: list[tuple[str, str]]) -> None:
        self._beta_page.set_monitor_choices(choices)

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

    def allow_close_once(self) -> None:
        self._allow_close_once = True


