Warning: truncated output (original token count: 17536)
Total output lines: 1532

from __future__ import annotations

import re
import json
import signal
import sys
import shutil
import ctypes
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRunnable, QRect, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon

from .app_metadata import APP_VERSION
from .app_settings import AppSettings, BetaZoomSettings, GameProfile, ThemeMode
from .config import OverlayShape, OverlayStyle
from .config_manager import ConfigManager
from .creator.conversion import creator_to_overlay_style, overlay_style_to_creator
from .creator.io import load_creator_crosshair, save_creator_crosshair
from .creator.models import CreatorCrosshair
from .crosshairs import (
    CrosshairDefinition,
    CrosshairLibrary,
    default_style_id,
    load_xhair,
    load_xpack,
    save_xpack,
    save_xhair,
    style_with_updates,
)
from .crosshairs.io import XHAIR_EXTENSION, XPACK_EXTENSION
from .hotkey_utils import is_hotkey_pressed, parse_hotkey
from .overlay_window import OverlayWindow
from .zoom_overlay_window import ZoomOverlayWindow
from .storage_paths import StoragePaths
from .style_registry import load_style_pack, save_style_pack
from .theme_manager import ThemeManager
from .update_manager import ReleaseInfo, UpdateError, UpdateManager
from .game_services import DiscoveredGame, scan_game_libraries
from .windows_runtime import (
    foreground_monitor_bounds,
    foreground_window_bounds,
    is_foreground_fullscreen,
    running_process_names,
)
from .ui.main_window import MainWindow
from .ui.react_surface import register_react_scheme
from .ui.pages.games_page import GameRowModel

try:
    import winreg
except Exception:  # noqa: BLE001
    winreg = None


class _WorkerSignals(QObject):
    finished = Signal(object)
    progress = Signal(int, int)


class _WorkerReaper(QObject):
    released = Signal(object)


class _ReleaseCheckWorker(QRunnable):
    def __init__(self, update_manager: UpdateManager, timeout_s: float = 6.0) -> None:
        super().__init__()
        self.update_manager = update_manager
        self.timeout_s = timeout_s
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self.update_manager.fetch_latest_release(timeout_s=self.timeout_s)
        except Exception as exc:  # a network failure must not freeze startup
            result = exc
        self.signals.finished.emit(result)


class _DownloadUpdateWorker(QRunnable):
    def __init__(self, update_manager: UpdateManager, release: ReleaseInfo) -> None:
        super().__init__()
        self.update_manager = update_manager
        self.release = release
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            last_reported = 0

            def report_progress(downloaded: int, total: int) -> None:
                nonlocal last_reported
                step = max(1_048_576, total // 100) if total else 1_048_576
                if downloaded - last_reported >= step or (total and downloaded >= total):
                    last_reported = downloaded
                    self.signals.progress.emit(downloaded, total)

            installer = self.update_manager.download_installer(
                self.release,
                progress_callback=report_progress,
            )
            self.update_manager.schedule_silent_update(installer)
            result: object = installer
        except Exception as exc:
            result = exc
        self.signals.finished.emit(result)


class _GameScanWorker(QRunnable):
    def __init__(self, generation: int) -> None:
        super().__init__()
        self.generation = generation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result: object = scan_game_libraries()
        except Exception as exc:
            result = exc
        self.signals.finished.emit((self.generation, result))


class AppController(QObject):
    """Coordinates app shell, overlay state, and persistence."""

    def __init__(self, app: QApplication, start_to_tray: bool = False) -> None:
        super().__init__()
        self._app = app
        self._workers: dict[int, QRunnable] = {}
        self._worker_reaper = _WorkerReaper(self)
        self._worker_reaper.released.connect(self._forget_worker, Qt.ConnectionType.QueuedConnection)
        self._config = ConfigManager()
        self._settings = self._config.load()
        self._storage_paths = StoragePaths(Path(self._settings.crosshair_storage_path))
        self._storage_paths.ensure()
        self._theme_manager = ThemeManager(app=self._app)
        self._update_manager = UpdateManager()

        self._library = CrosshairLibrary()
        self._definitions = self._library.load(self._storage_paths.root)
        self._hydrate_favorites()

        self._current_style_id = self._validated_style_id(self._settings.selected_style_id)
        self._overlay = OverlayWindow(style=self._effective_style())
        self._zoom_overlay = ZoomOverlayWindow()
        self._main_window = MainWindow(
            definitions=self._definitions,
            current_style_id=self._current_style_id,
            selected_size_percent=self._settings.selected_size_percent,
            theme_mode=self._settings.theme_mode,
            accent_color=self._settings.accent_color,
            global_size_percent=self._settings.global_size_percent,
            storage_path=self._settings.crosshair_storage_path,
            beta_features_enabled=self._settings.beta_zoom.sidebar_enabled,
            auto_update_on_startup=self._settings.auto_update_on_startup,
            run_on_startup_tray=self._settings.run_on_startup_tray,
            beta_zoom_settings=self._settings.beta_zoom,
            sidebar_collapsed=self._settings.sidebar_collapsed,
        )
        self._start_to_tray = bool(start_to_tray)
        self._update_available_on_startup = False
        self._overlay_visible = bool(self._settings.overlay_enabled)
        self._manual_overlay_enabled = bool(self._settings.overlay_enabled)
        self._manual_style_id = self._current_style_id
        self._auto_applied_style_id: str | None = None
        self._active_game_profile_id: str | None = None
        self._last_fullscreen_state = False
        self._last_game_monitor_bounds: tuple[int, int, int, int] | None = None
        self._last_game_window_bounds: tuple[int, int, int, int] | None = None
        self._discovered_games: list[DiscoveredGame] = []
        self._game_scan_generation = 0
        self._game_scan_running = False
        self._game_scan_pending = False
        self._automation_timer = QTimer(self)
        self._automation_timer.setInterval(1100)
        self._automation_timer.timeout.connect(self._automation_tick)
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setTimerType(Qt.TimerType.PreciseTimer)
        # 30 Hz keeps the hotkey responsive and caps expensive desktop captures
        # at a useful preview rate (the previous 125 Hz rate was wasteful).
        self._zoom_timer.setInterval(33)
        self._zoom_timer.timeout.connect(self._zoom_tick)
        self._zoom_hotkey = parse_hotkey(self._settings.beta_zoom.hotkey_sequence)
        self._zoom_showing = False
        self._last_overlay_bounds: tuple[int, int, int, int] | None = None
        self._last_runtime_status = ""
        self._update_check_running = False
        self._manual_update_progress: QProgressDialog | None = None
        self._manual_update_options = (False, False)
        self._download_progress: QProgressDialog | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._is_quitting = False
        self._wire_signals()
        self._apply_theme()
        self._sync_windows_autostart_setting()
        self._reload_games()
        self._setup_tray()
        if hasattr(self._app, "screenAdded"):
            self._app.screenAdded.connect(lambda _screen: self._refresh_beta_monitor_choices())
        if hasattr(self._app, "screenRemoved"):
            self._app.screenRemoved.connect(lambda _screen: self._refresh_beta_monitor_choices())

    def _wire_signals(self) -> None:
        self._main_window.enable_overlay_requested.connect(self.show_overlay)
        self._main_window.disable_overlay_requested.connect(self.hide_overlay)
        self._main_window.quit_requested.connect(self.quit_application)
        self._main_window.style_selected.connect(self.set_overlay_style)
        self._main_window.style_detail_requested.connect(self.open_style_detail)
        self._main_window.style_favorite_toggled.connect(self.toggle_favorite)
        self._main_window.style_live_updated.connect(self.apply_live_style_update)
        self._main_window.style_variant_save_requested.connect(self.save_style_variant)
        self._main_window.style_export_requested.connect(self.export_style_definition)
        self._main_window.selected_size_changed.connect(self.set_selected_size)
        self._main_window.theme_mode_changed.connect(self.set_theme_mode)
        self._main_window.accent_color_changed.connect(self.set_accent_color)
        self._main_window.global_size_changed.connect(self.set_global_size)
        self._main_window.storage_path_changed.connect(self.set_storage_path)
        self._main_window.reset_requested.connect(self.reset_settings)
        self._main_window.check_updates_requested.connect(self.check_for_updates)
        self._main_window.auto_update_on_startup_changed.connect(self.set_auto_update_on_startup)
        self._main_window.run_on_startup_tray_changed.connect(self.set_run_on_startup_tray)
        self._main_window.import_pack_requested.connect(self.import_pack)
        self._main_window.export_pack_requested.connect(self.export_current_style)
        self._main_window.export_selection_requested.connect(self.export_selected_pack)
        self._main_window.creator_save_requested.connect(self.save_creator_crosshair)
        self._main_window.creator_export_requested.connect(self.export_creator_crosshair)
        self._main_window.send_to_editor_requested.connect(self.send_style_to_editor)
        self._main_window.sidebar_collapsed_changed.connect(self.set_sidebar_collapsed)
        self._main_window.fullscreen_auto_toggled.connect(self.set_auto_enable_on_fullscreen)
        self._main_window.game_auto_switch_toggled.connect(self.set_auto_switch_game_profiles)
        self._main_window.game_profile_updated.connect(self.update_game_profile)
        self._main_window.import_game_requested.connect(self.import_manual_game)
        self._main_window.rescan_games_requested.connect(self.rescan_games)
        self._main_window.beta_features_changed.connect(self.set_beta_features_enabled)
        self._main_window.beta_zoom_settings_changed.connect(self.set_beta_zoom_settings)
        self._main_window.close_to_tray_requested.connect(self.hide_main_window_to_tray)

    def _start_worker(self, worker: QRunnable) -> None:
        worker_key = id(worker)
        self._workers[worker_key] = worker
        worker.signals.finished.connect(lambda *_args, key=worker_key: self._worker_reaper.released.emit(key))
        QThreadPool.globalInstance().start(worker)

    def _forget_worker(self, worker_key: int) -> None:
        self._workers.pop(worker_key, None)

    def start(self) -> None:
        if self._overlay_visible:
            self._overlay.show()
            self._main_window.set_overlay_status(True)
        else:
            self._overlay.hide()
            self._main_window.set_overlay_status(False)

        should_start_hidden = self._start_to_tray and self._settings.run_on_startup_tray and self._tray_icon is not None
        if should_start_hidden:
            self._main_window.hide()
        else:
            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()
        self._main_window.set_selected_style(self._current_style_id)
        self._main_window.set_selected_style_name(self._definitions[self._current_style_id].display_name)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._main_window.set_selected_size(self._settings.selected_size_percent)
        self._main_window.set_global_size(self._settings.global_size_percent)
        self._main_window.set_storage_path(self._settings.crosshair_storage_path)
        self._main_window.set_beta_page_visible(self._settings.beta_zoom.sidebar_enabled)
        self._main_window.set_beta_zoom_settings(self._settings.beta_zoom)
        self._main_window.set_startup_preferences(
            auto_update_on_startup=self._settings.auto_update_on_startup,
            run_on_startup_tray=self._settings.run_on_startup_tray,
        )
        self._main_window.set_update_available(False)
        self._refresh_beta_monitor_choices()
        self._refresh_games_page()
        self._main_window.navigate_to("home")
        self._automation_timer.start()
        self._zoom_timer.start()
        self._automation_tick()
        self._zoom_tick()
        if self._tray_icon is not None:
            self._tray_icon.show()
        QTimer.singleShot(1400, self._check_updates_on_startup)

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self._app.windowIcon()
        self._tray_icon = QSystemTrayIcon(icon, self._main_window)
        self._tray_icon.setToolTip("Crosshair Overlay")

        self._tray_menu = QMenu(self._main_window)
        action_show = QAction("Show Window", self._tray_menu)
        action_hide = QAction("Hide Window", self._tray_menu)
        action_enable = QAction("Enable Overlay", self._tray_menu)
        action_disable = QAction("Disable Overlay", self._tray_menu)
        action_quit = QAction("Quit", self._tray_menu)

        action_show.triggered.connect(self.show_main_window)
        action_hide.triggered.connect(self.hide_main_window_to_tray)
        action_enable.triggered.connect(self.show_overlay)
        action_disable.triggered.connect(self.hide_overlay)
        action_quit.triggered.connect(self.quit_application)

        self._tray_menu.addAction(action_show)
        self._tray_menu.addAction(action_hide)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction(action_enable)
        self._tray_menu.addAction(action_disable)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction(action_quit)

        self._tray_icon.setContextMenu(self._tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick}:
            if self._main_window.isVisible():
                self.hide_main_window_to_tray()
            else:
                self.show_main_window()

    def show_main_window(self) -> None:
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def hide_main_window_to_tray(self) -> None:
        if not self._main_window.isVisible():
            return
        self._main_window.hide()
        if self._tray_icon is not None:
            self._tray_icon.showMessage(
                "Crosshair Overlay",
                "Still running in system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )

    def show_overlay(self) -> None:
        self._manual_overlay_enabled = True
        self._set_overlay_visible(True, persist=True)

    def hide_overlay(self) -> None:
        self._manual_overlay_enabled = False
        self._set_overlay_visible(False, persist=True)

    def set_overlay_style(self, style_id: str, persist: bool = True) -> None:
        if style_id not in self._definitions:
            return
        self._current_style_id = style_id
        if persist:
            self._settings.selected_style_id = style_id
            self._manual_style_id = style_id
        self._overlay.set_style(self._effective_style())
        self._main_window.set_selected_style(style_id)
        self._main_window.set_selected_style_name(self._definitions[style_id].display_name)
        self._main_window.set_active_style_preview(self._definitions[style_id])
        self._main_window.set_detail_definition(self._definitions[style_id])
        if persist:
            self._save_settings()

    def open_style_detail(self, style_id: str) -> None:
        if style_id not in self._definitions:
            return
        self._main_window.set_detail_definition(self._definitions[style_id])

    def apply_live_style_update(self, definition: object) -> None:
        if not isinstance(definition, CrosshairDefinition):
            return
        self._definitions[definition.style_id] = definition
        self._library.upsert_runtime_definition(definition)
        if definition.style_id == self._current_style_id:
            self._overlay.set_style(self._effective_style())
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id, catalog_changed=False)
        self._main_window.set_detail_definition(definition)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])

    def save_style_variant(self, definition: object) -> None:
        if not isinstance(definition, CrosshairDefinition):
            return
        try:
            name = definition.display_name.strip() or "Custom Crosshair"
            style_id = self._slugify(name)
            style = style_with_updates(definition.style, {"style_id": style_id, "display_name": name})
            custom = CrosshairDefinition(
                style=style,
                family=f"{definition.family} Variant",
                description=f"Custom variant of {definition.display_name}.",
                tags=tuple(set(definition.tags + ("variant", "custom"))),
                editable_settings=definition.editable_settings,
                source_type="custom",
            )
            saved = self._library.save_custom_definition(custom, Path(self._settings.crosshair_storage_path))
            self._definitions = self._library.definitions
            self._main_window.refresh_definitions(self._definitions, selected_style_id=saved.style_id)
            self.set_overlay_style(saved.style_id)
            self._refresh_games_page()
            QMessageBox.information(self._main_window, "Saved", f"Saved variant '{saved.display_name}'.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Save Failed", f"Could not save variant.\n{exc}")

    def toggle_favorite(self, style_id: str) -> None:
        if style_id not in self._definitions:
            return
        current = self._definitions[style_id].is_favorite
        self._library.set_favorite(style_id, not current)
        self._definitions = self._library.definitions
        favorites = [item.style_id for item in self._definitions.values() if item.is_favorite]
        self._settings.favorite_style_ids = favorites
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._save_settings()

    def set_selected_size(self, value: int) -> None:
        bounded = max(50, min(200, int(value)))
        self._settings.selected_size_percent = bounded
        self._overlay.set_style(self._effective_style())
        self._main_window.set_selected_size(bounded)
        self._save_settings()

    def set_global_size(self, value: int) -> None:
        bounded = max(50, min(200, int(value)))
        self._settings.global_size_percent = bounded
        self._overlay.set_style(self._effective_style())
        self._main_window.set_global_size(bounded)
        self._save_settings()

    def set_theme_mode(self, mode: str) -> None:
        if mode not in {ThemeMode.SYSTEM.value, ThemeMode.DARK.value, ThemeMode.LIGHT.value}:
            mode = ThemeMode.SYSTEM.value
        self._settings.theme_mode = mode
        self._apply_theme()
        self._save_settings()

    def cycle_theme_mode(self) -> None:
        order = [ThemeMode.SYSTEM.value, ThemeMode.DARK.value, ThemeMode.LIGHT.value]
        try:
            idx = order.index(self._settings.theme_mode)
        except ValueError:
            idx = 0
        self.set_theme_mode(order[(idx + 1) % len(order)])

    def set_auto_update_on_startup(self, enabled: bool) -> None:
        self._settings.auto_update_on_startup = bool(enabled)
        self._main_window.set_startup_preferences(
            auto_update_on_startup=self._settings.auto_update_on_startup,
            run_on_startup_tray=self._settings.run_on_startup_tray,
        )
        self._save_settings()

    def set_run_on_startup_tray(self, enabled: bool) -> None:
        self._settings.run_on_startup_tray = bool(enabled)
        self._main_window.set_startup_preferences(
            auto_update_on_startup=self._settings.auto_update_on_startup,
            run_on_startup_tray=self._settings.run_on_startup_tray,
        )
        self._sync_windows_autostart_setting()
        self._save_settings()

    def set_accent_color(self, color_hex: str) -> None:
        self._settings.accent_color = color_hex.upper()
        self._apply_theme()
        self._save_settings()

    def set_storage_path(self, path: str) -> None:
        storage = Path(path)
        storage.mkdir(parents=True, exist_ok=True)
        self._settings.crosshair_storage_path = str(storage)
        self._definitions = self._library.load(storage)
        self._storage_paths = StoragePaths(storage)
        self._storage_paths.ensure()
        self._hydrate_favorites()
        self._current_style_id = self._validated_style_id(self._current_style_id)
        self._manual_style_id = self._validated_style_id(self._manual_style_id)
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id)
        self._main_window.set_storage_path(str(storage))
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._overlay.set_style(self._effective_style())
        self._refresh_games_page()
        self._save_settings()

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._settings.sidebar_collapsed = collapsed
        self._save_settings()

    def set_beta_features_enabled(self, enabled: bool) -> None:
        self._settings.beta_zoom.sidebar_enabled = bool(enabled)
        self._main_window.set_beta_page_visible(self._settings.beta_zoom.sidebar_enabled)
        self._refresh_beta_monitor_choices()
        if not self._settings.beta_zoom.sidebar_enabled:
            self._hide_zoom_overlay()
        self._save_settings()

    def set_beta_zoom_settings(self, settings: object) -> None:
        if not isinstance(settings, BetaZoomSettings):
            return
        normalized = self._normalized_beta_zoom_settings(settings)
        self._settings.beta_zoom = normalized
        self._zoom_hotkey = parse_hotkey(normalized.hotkey_sequence)
        self._main_window.set_beta_zoom_settings(normalized)
        if not normalized.zoom_enabled and not normalized.live_enabled:
            self._hide_zoom_overlay()
        self._save_settings()

    def import_pack(self, pack_path: str) -> None:
        try:
            source = Path(p…5536 tokens truncated…name.strip().lower()
            profile.executable_names = [executable_name] if executable_name else []

        profile.style_id = style_id if style_id in self._definitions else ""
        profile.enabled = bool(enabled and profile.style_id)
        self._refresh_games_page()
        self._save_settings()

    def import_manual_game(self, executable_path: str) -> None:
        path = Path(executable_path)
        if not path.exists() or path.suffix.lower() != ".exe":
            QMessageBox.warning(self._main_window, "Import Game", "Please select a valid game executable (.exe).")
            return
        game_id = f"manual:{path.stem.lower()}"
        profile = self._profile_for_game(game_id)
        if profile is None:
            profile = GameProfile(
                game_id=game_id,
                title=path.stem,
                source="manual",
                executable_names=[path.name.lower()],
                executable_path=str(path),
                icon_path=str(path),
                style_id="",
                enabled=False,
            )
            self._settings.game_profiles.append(profile)
        else:
            profile.title = path.stem
            profile.source = "manual"
            profile.executable_names = [path.name.lower()]
            profile.executable_path = str(path)
            profile.icon_path = str(path)

        self._refresh_games_page()
        self._save_settings()

    def rescan_games(self) -> None:
        self._reload_games()
        self._refresh_games_page()

    def _reload_games(self) -> None:
        if self._game_scan_running:
            self._game_scan_pending = True
            return
        self._game_scan_running = True
        self._game_scan_generation += 1
        worker = _GameScanWorker(self._game_scan_generation)
        worker.signals.finished.connect(self._handle_game_scan_result)
        self._start_worker(worker)

    def _handle_game_scan_result(self, payload: object) -> None:
        self._game_scan_running = False
        if isinstance(payload, tuple) and len(payload) == 2:
            generation, result = payload
            if generation == self._game_scan_generation and isinstance(result, list):
                self._discovered_games = result
                self._sync_profiles_with_discovery()
                self._refresh_games_page()
        if self._game_scan_pending:
            self._game_scan_pending = False
            self._reload_games()

    def _sync_profiles_with_discovery(self) -> None:
        profile_map = {profile.game_id: profile for profile in self._settings.game_profiles}
        for game in self._discovered_games:
            profile = profile_map.get(game.game_id)
            if profile is None:
                continue
            profile.title = game.title
            profile.source = game.source
            profile.executable_path = game.executable_path
            profile.icon_path = game.icon_path
            exe_name = game.executable_name.strip().lower()
            profile.executable_names = [exe_name] if exe_name else []

    def _refresh_games_page(self) -> None:
        profile_map = {profile.game_id: profile for profile in self._settings.game_profiles}
        rows: list[GameRowModel] = []
        for game in self._all_games():
            profile = profile_map.get(game.game_id)
            assigned_style_id = profile.style_id if profile and profile.style_id in self._definitions else ""
            rows.append(
                GameRowModel(
                    game_id=game.game_id,
                    title=game.title,
                    source=game.source,
                    executable_path=game.executable_path,
                    icon_path=game.icon_path,
                    assigned_style_id=assigned_style_id,
                    enabled=bool(profile.enabled) if profile else False,
                )
            )
        style_items = [(definition.style_id, definition.display_name) for definition in self._definitions.values()]
        self._main_window.set_games_data(games=rows, style_items=style_items)
        self._main_window.set_games_toggles(
            fullscreen_enabled=self._settings.auto_enable_on_fullscreen,
            game_switch_enabled=self._settings.auto_switch_game_profiles,
        )
        self._main_window.set_games_status(self._current_runtime_status())

    def _refresh_beta_monitor_choices(self) -> None:
        self._main_window.set_beta_monitor_choices(self._monitor_choices())

    def _monitor_choices(self) -> list[tuple[str, str]]:
        choices = [("same_as_game", "Same as Game Monitor")]
        screens = self._app.screens()
        primary = self._app.primaryScreen()
        for index, screen in enumerate(screens):
            geometry = screen.geometry()
            name = screen.name().strip() or f"Monitor {index + 1}"
            prefix = "Primary" if screen == primary else f"Monitor {index + 1}"
            label = f"{prefix} - {name} ({geometry.width()}x{geometry.height()})"
            choices.append((f"screen:{index}", label))
        return choices

    def _automation_tick(self) -> None:
        running_names: set[str] = set()
        try:
            running_names = running_process_names()
        except Exception:
            running_names = set()

        fullscreen = False
        try:
            fullscreen = is_foreground_fullscreen()
        except Exception:
            fullscreen = False

        self._last_fullscreen_state = fullscreen
        monitor_bounds: tuple[int, int, int, int] | None = None
        try:
            monitor_bounds = foreground_monitor_bounds()
        except Exception:
            monitor_bounds = None
        window_bounds: tuple[int, int, int, int] | None = None
        try:
            window_bounds = foreground_window_bounds()
        except Exception:
            window_bounds = None

        active_profile = self._resolve_active_game_profile(running_names)
        if monitor_bounds is not None and fullscreen:
            self._last_game_monitor_bounds = monitor_bounds
        if window_bounds is not None and fullscreen:
            self._last_game_window_bounds = window_bounds

        should_show_overlay = self._manual_overlay_enabled
        if self._settings.auto_enable_on_fullscreen:
            should_show_overlay = fullscreen
        if self._settings.auto_switch_game_profiles and active_profile is not None:
            should_show_overlay = True

        self._set_overlay_visible(should_show_overlay, persist=False)

        if self._overlay_visible:
            overlay_bounds = monitor_bounds
            if overlay_bounds is None:
                screen = self._app.primaryScreen()
                if screen is not None:
                    geometry = screen.geometry()
                    overlay_bounds = (geometry.x(), geometry.y(), geometry.x() + geometry.width(), geometry.y() + geometry.height())
            if overlay_bounds is not None and overlay_bounds != self._last_overlay_bounds:
                self._overlay.center_on_bounds(*overlay_bounds)
                self._last_overlay_bounds = overlay_bounds

        if self._settings.auto_switch_game_profiles and active_profile is not None:
            if active_profile.style_id in self._definitions:
                if self._active_game_profile_id != active_profile.game_id:
                    self._active_game_profile_id = active_profile.game_id
                    self._auto_applied_style_id = active_profile.style_id
                    self.set_overlay_style(active_profile.style_id, persist=False)
        else:
            self._restore_manual_style_if_needed()
            self._active_game_profile_id = None

        runtime_status = self._current_runtime_status()
        if runtime_status != self._last_runtime_status:
            self._main_window.set_games_status(runtime_status)
            self._last_runtime_status = runtime_status

    def _zoom_tick(self) -> None:
        show_preview = (
            self._settings.beta_zoom.sidebar_enabled
            and self._main_window.isVisible()
            and self._main_window.current_page_id == "beta"
        )
        live_zoom_enabled = self._settings.beta_zoom.sidebar_enabled and self._settings.beta_zoom.live_enabled
        allow_zoom = self._settings.beta_zoom.sidebar_enabled and self._settings.beta_zoom.zoom_enabled
        hotkey_down = allow_zoom and is_hotkey_pressed(self._zoom_hotkey)
        if not show_preview and not live_zoom_enabled and not hotkey_down:
            self._hide_zoom_overlay()
            return

        source_frame = self._current_zoom_source_frame()
        source_screen = self._screen_for_frame(source_frame)
        if source_screen is None:
            if show_preview:
                self._main_window.set_beta_preview(None)
            self._hide_zoom_overlay()
            return

        target_screen = self._target_zoom_screen(source_screen, source_frame)
        if target_screen is None:
            if show_preview:
                self._main_window.set_beta_preview(None)
            self._hide_zoom_overlay()
            return

        capture_point = self._current_zoom_capture_point(source_screen, source_frame)
        target_rect = self._zoom_target_rect(target_screen, capture_point)
        if target_rect is None:
            if show_preview:
                self._main_window.set_beta_preview(None)
            self._hide_zoom_overlay()
            return

        avoid_zoom_feedback = target_screen == source_screen
        pixmap = self._capture_zoom_pixmap(
            source_screen,
            source_frame,
            capture_point,
            target_rect.size(),
            avoid_zoom_feedback=avoid_zoom_feedback,
        )
        if show_preview:
            self._main_window.set_beta_preview(pixmap)

        if pixmap is None or pixmap.isNull():
            self._hide_zoom_overlay()
            return

        if not live_zoom_enabled and not hotkey_down:
            self._hide_zoom_overlay()
            return

        animate = bool(self._settings.beta_zoom.animation_enabled and not self._zoom_showing)
        self._zoom_overlay.show_zoom(
            pixmap=pixmap,
            target_rect=target_rect,
            animate=animate,
            duration_ms=self._settings.beta_zoom.animation_duration_ms,
        )
        self._zoom_showing = True

    def _current_zoom_source_frame(self) -> tuple[int, int, int, int] | None:
        live_window_bounds: tuple[int, int, int, int] | None = None
        try:
            live_window_bounds = foreground_window_bounds()
        except Exception:
            live_window_bounds = None

        if self._last_fullscreen_state and live_window_bounds is not None:
            return live_window_bounds
        if self._last_game_window_bounds is not None:
            return self._last_game_window_bounds

        live_monitor_bounds: tuple[int, int, int, int] | None = None
        try:
            live_monitor_bounds = foreground_monitor_bounds()
        except Exception:
            live_monitor_bounds = None

        if self._last_fullscreen_state and live_monitor_bounds is not None:
            return live_monitor_bounds
        if self._last_game_monitor_bounds is not None:
            return self._last_game_monitor_bounds
        if live_monitor_bounds is not None:
            return live_monitor_bounds

        primary = self._app.primaryScreen()
        if primary is None:
            return None
        geometry = primary.geometry()
        return (geometry.x(), geometry.y(), geometry.x() + geometry.width(), geometry.y() + geometry.height())

    def _screen_for_frame(self, frame: tuple[int, int, int, int] | None):
        if frame is None:
            return None
        center_x = frame[0] + max(1, frame[2] - frame[0]) // 2
        center_y = frame[1] + max(1, frame[3] - frame[1]) // 2
        point = QPoint(center_x, center_y)
        for screen in self._app.screens():
            if screen.geometry().contains(point):
                return screen
        return self._app.primaryScreen()

    def _target_zoom_screen(self, source_screen, source_frame: tuple[int, int, int, int] | None):
        if self._settings.beta_zoom.display_mode == "crosshair":
            if source_screen is not None:
                return source_screen
            return self._screen_for_frame(source_frame)
        monitor_id = self._settings.beta_zoom.target_monitor_id
        if monitor_id != "same_as_game" and monitor_id.startswith("screen:"):
            try:
                index = int(monitor_id.split(":", 1)[1])
            except ValueError:
                index = -1
            screens = self._app.screens()
            if 0 <= index < len(screens):
                return screens[index]
        if source_screen is not None:
            return source_screen
        return self._screen_for_frame(source_frame)

    def _current_zoom_capture_point(self, source_screen, source_frame: tuple[int, int, int, int] | None) -> QPoint | None:
        if source_screen is None:
            return None

        screen_geometry = source_screen.geometry()
        if source_frame is None:
            frame_rect = screen_geometry
        else:
            frame_rect = QRect(
                source_frame[0],
                source_frame[1],
                max(1, source_frame[2] - source_frame[0]),
                max(1, source_frame[3] - source_frame[1]),
            ).intersected(screen_geometry)
            if frame_rect.isEmpty():
                frame_rect = screen_geometry

        crosshair_point = self._overlay.crosshair_center()
        if frame_rect.contains(crosshair_point):
            return crosshair_point
        if screen_geometry.contains(crosshair_point):
            clamped_x = max(frame_rect.left(), min(crosshair_point.x(), frame_rect.right()))
            clamped_y = max(frame_rect.top(), min(crosshair_point.y(), frame_rect.bottom()))
            return QPoint(clamped_x, clamped_y)
        return frame_rect.center()

    def _zoom_target_rect(self, target_screen, capture_point: QPoint | None) -> QRect | None:
        if target_screen is None:
            return None
        geometry = target_screen.geometry()
        min_edge = max(220, min(geometry.width(), geometry.height()))
        if self._settings.beta_zoom.display_mode == "crosshair":
            side = max(180, min(380, int(round(min_edge * 0.24))))
        else:
            side = max(260, min(720, int(round(min_edge * 0.34))))
        side = min(side, geometry.width(), geometry.height())
        if self._settings.beta_zoom.display_mode == "crosshair":
            anchor = capture_point or geometry.center()
            x = anchor.x() - (side // 2)
            y = anchor.y() - (side // 2)
            x = max(geometry.left(), min(x, geometry.right() - side + 1))
            y = max(geometry.top(), min(y, geometry.bottom() - side + 1))
            return QRect(x, y, side, side)
        available_width = max(0, geometry.width() - side)
        available_height = max(0, geometry.height() - side)
        x = geometry.x() + int(round((available_width * self._settings.beta_zoom.position_x_percent) / 100))
        y = geometry.y() + int(round((available_height * self._settings.beta_zoom.position_y_percent) / 100))
        return QRect(x, y, side, side)

    def _capture_zoom_pixmap(
        self,
        source_screen,
        source_frame: tuple[int, int, int, int] | None,
        capture_point: QPoint | None,
        output_size: QSize,
        avoid_zoom_feedback: bool = False,
    ) -> QPixmap | None:
        if source_screen is None or source_frame is None:
            return None

        screen_geometry = source_screen.geometry()
        frame_rect = QRect(
            source_frame[0],
            source_frame[1],
            max(1, source_frame[2] - source_frame[0]),
            max(1, source_frame[3] - source_frame[1]),
        ).intersected(screen_geometry)
        if frame_rect.isEmpty():
            frame_rect = screen_geometry

        side = max(120, min(output_size.width(), output_size.height()))
        zoom_factor = max(2.0, self._settings.beta_zoom.zoom_percent / 100.0)
        capture_side = max(18, int(round(side / zoom_factor)))
        capture_side = min(capture_side, frame_rect.width(), frame_rect.height())
        if capture_side <= 0:
            return None

        anchor = capture_point or frame_rect.center()
        capture_x = anchor.x() - (capture_side // 2)
        capture_y = anchor.y() - (capture_side // 2)
        capture_x = max(frame_rect.left(), min(capture_x, frame_rect.right() - capture_side + 1))
        capture_y = max(frame_rect.top(), min(capture_y, frame_rect.bottom() - capture_side + 1))

        local_x = capture_x - screen_geometry.x()
        local_y = capture_y - screen_geometry.y()
        return source_screen.grabWindow(0, local_x, local_y, capture_side, capture_side)

    def _hide_zoom_overlay(self) -> None:
        if self._zoom_showing:
            self._zoom_overlay.hide_zoom()
        self._zoom_showing = False

    def _resolve_active_game_profile(self, running_names: set[str]) -> GameProfile | None:
        if not running_names:
            return None
        profiles = [profile for profile in self._settings.game_profiles if profile.enabled and profile.style_id]
        for profile in profiles:
            for executable in profile.executable_names:
                if executable and executable.lower() in running_names:
                    return profile
            if profile.executable_path:
                name = Path(profile.executable_path).name.lower()
                if name and name in running_names:
                    return profile
        return None

    def _restore_manual_style_if_needed(self) -> None:
        if self._auto_applied_style_id is None:
            return
        self._auto_applied_style_id = None
        if self._manual_style_id in self._definitions and self._current_style_id != self._manual_style_id:
            self.set_overlay_style(self._manual_style_id, persist=False)

    def _all_games(self) -> list[DiscoveredGame]:
        merged: list[DiscoveredGame] = list(self._discovered_games)
        known_ids = {game.game_id for game in merged}
        for profile in self._settings.game_profiles:
            if profile.game_id in known_ids:
                continue
            merged.append(
                DiscoveredGame(
                    game_id=profile.game_id,
                    title=profile.title or profile.game_id,
                    source=profile.source or "manual",
                    executable_path=profile.executable_path,
                    executable_name=Path(profile.executable_path).name.lower() if profile.executable_path else "",
                    icon_path=profile.icon_path,
                )
            )
        return sorted(merged, key=lambda game: (game.source, game.title.lower()))

    def _profile_for_game(self, game_id: str) -> GameProfile | None:
        for profile in self._settings.game_profiles:
            if profile.game_id == game_id:
                return profile
        return None

    def _current_runtime_status(self) -> str:
        fullscreen_text = "fullscreen detected" if self._last_fullscreen_state else "windowed mode"
        if self._active_game_profile_id:
            active_profile = self._profile_for_game(self._active_game_profile_id)
            if active_profile:
                return f"Runtime: {fullscreen_text}. Active game: {active_profile.title}."
        return f"Runtime: {fullscreen_text}. No mapped game currently running."

    def _set_overlay_visible(self, visible: bool, persist: bool) -> None:
        if self._overlay_visible != visible:
            if visible:
                self._overlay.show()
                self._overlay.raise_()
            else:
                self._overlay.hide()
                self._last_overlay_bounds = None
            self._overlay_visible = visible
        if persist:
            self._settings.overlay_enabled = visible
            self._save_settings()
        self._main_window.set_overlay_status(self._overlay_visible)

    def quit_application(self) -> None:
        if self._is_quitting:
            return
        self._is_quitting = True
        self._automation_timer.stop()
        self._zoom_timer.stop()
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self._hide_zoom_overlay()
        self._zoom_overlay.close()
        self._overlay.close()
        self._main_window.allow_close_once()
        self._main_window.close()
        self._app.quit()

    def _validated_style_id(self, style_id: str) -> str:
        return self._library.ensure_style_id(style_id)

    def _effective_style(self) -> OverlayStyle:
        base = self._definitions[self._current_style_id].style
        combined = int(round((self._settings.selected_size_percent * self._settings.global_size_percent) / 100))
        return base.scaled(max(50, min(220, combined)))

    def _apply_theme(self) -> None:
        self._theme_manager.apply(theme_mode=self._settings.theme_mode, accent_hex=self._settings.accent_color)
        self._main_window.set_theme_values(self._settings.theme_mode, self._settings.accent_color, self._theme_manager.resolved_mode.value)
        self._main_window.set_beta_page_visible(self._settings.beta_zoom.sidebar_enabled)

    def _save_settings(self) -> None:
        self._config.save(self._settings)

    def _hydrate_favorites(self) -> None:
        favorite_set = set(self._settings.favorite_style_ids)
        for style_id in list(self._definitions.keys()):
            if style_id in favorite_set:
                self._definitions[style_id] = self._definitions[style_id].with_favorite(True)

    def _slugify(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_\-\s]", "", value).strip().lower()
        normalized = re.sub(r"[\s\-]+", "_", normalized)
        return normalized or "custom_crosshair"

    def _normalized_beta_zoom_settings(self, settings: BetaZoomSettings) -> BetaZoomSettings:
        sequence = settings.hotkey_sequence.strip()
        display_mode = settings.display_mode.strip().lower()
        if display_mode not in {"crosshair", "monitor"}:
            display_mode = "monitor"
        monitor_id = settings.target_monitor_id.strip() or "same_as_game"
        return BetaZoomSettings(
            sidebar_enabled=self._settings.beta_zoom.sidebar_enabled,
            live_enabled=bool(settings.live_enabled),
            zoom_enabled=bool(settings.zoom_enabled),
            hotkey_sequence=sequence,
            display_mode=display_mode,
            target_monitor_id=monitor_id,
            position_x_percent=max(0, min(100, int(settings.position_x_percent))),
            position_y_percent=max(0, min(100, int(settings.position_y_percent))),
            zoom_percent=max(200, min(10000, int(settings.zoom_percent))),
            animation_enabled=bool(settings.animation_enabled),
            animation_duration_ms=max(0, min(5000, int(settings.animation_duration_ms))),
        )


def run() -> int:
    """Application entry point."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CrosshairOverlay.App")
        except Exception:
            pass

    register_react_scheme()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.svg"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    start_to_tray = "--tray-start" in {arg.strip().lower() for arg in sys.argv[1:]}
    controller = AppController(app=app, start_to_tray=start_to_tray)
    controller.start()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()

