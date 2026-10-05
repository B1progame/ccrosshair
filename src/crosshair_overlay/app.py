from __future__ import annotations

import re
import json
import signal
import sys
import shutil
import ctypes
import os
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QProcess, QRunnable, QRect, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QProgressDialog, QSystemTrayIcon

from .app_metadata import APP_VERSION
from .app_settings import AccessibilitySettings, AppSettings, BetaZoomSettings, GameLoadout, GameProfile, LibraryCollection, ReactiveSettings, ThemeMode
from .config import OverlayShape, OverlayStyle
from .config_manager import ConfigManager
from .creator.conversion import creator_to_overlay_style, overlay_style_to_creator
from .creator.io import load_creator_crosshair, save_creator_crosshair
from .creator.models import CreatorCrosshair, CreatorLayer
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
from .zoom_pipeline import ZoomFrameProcessor
from .mouse_wheel_hook import GlobalMouseWheelHook
from .zoom_controls import effective_zoom_max_percent, stepped_zoom_percent
from .runtime_adaptation import GpuRuntimeAdaptation
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
from .ui.models import GameRowModel

try:
    import winreg
except Exception:  # noqa: BLE001
    winreg = None


def _parse_optional_rgba(hex_color: str, base_rgba: tuple[int, int, int, int], opacity_percent: int) -> tuple[int, int, int, int]:
    """Apply a loadout's optional color and opacity without mutating its base style."""
    if isinstance(hex_color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        rgb = tuple(int(hex_color[index:index + 2], 16) for index in (1, 3, 5))
    else:
        rgb = base_rgba[:3]
    opacity = max(0, min(100, int(opacity_percent)))
    return (*rgb, round(base_rgba[3] * opacity / 100))


def _next_ads_state(mode: str, button_down: bool, previous_button_down: bool, toggled: bool) -> tuple[bool, bool]:
    """Return the new latch and active ADS state for hold or press-to-toggle input."""
    if mode == "toggle":
        next_toggled = not toggled if button_down and not previous_button_down else toggled
        return next_toggled, next_toggled
    return False, bool(button_down)


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
        self._zoom_processor = ZoomFrameProcessor()
        self._zoom_generation = 0
        self._zoom_capture_active = False
        self._zoom_target_rect_current: QRect | None = None
        self._zoom_effective_max_percent = 1600
        self._last_zoom_diagnostics_publish = 0.0
        self._gpu_runtime_adaptation = GpuRuntimeAdaptation()
        self._gpu_probe_timer = QTimer(self)
        self._gpu_probe_timer.setInterval(5000)
        self._gpu_probe_timer.timeout.connect(self._probe_gpu_runtime)
        self._gpu_probe = QProcess(self)
        self._gpu_probe.finished.connect(self._on_gpu_runtime_sample)
        self._gpu_probe.errorOccurred.connect(self._on_gpu_probe_error)
        self._zoom_processor.set_generation(self._zoom_generation)
        self._zoom_processor.frame_ready.connect(self._on_zoom_frame)
        self._zoom_processor.start()
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
            accessibility_settings=self._settings.accessibility,
            reactive_settings=self._settings.reactive,
            recent_style_ids=self._settings.recent_style_ids,
            recent_crosshair_colors=self._settings.recent_crosshair_colors,
        )
        self._main_window.set_quick_switch_hotkeys(
            self._settings.quick_switch_next_hotkey,
            self._settings.quick_switch_previous_hotkey,
            self._settings.quick_switch_favorite_hotkey,
        )
        self._main_window.set_monitor_offsets(self._settings.monitor_offsets)
        self._main_window.set_library_metadata(
            [asdict(item) for item in self._settings.library_collections], self._settings.library_tags)
        self._start_to_tray = bool(start_to_tray)
        self._update_available_on_startup = False
        self._overlay_visible = bool(self._settings.overlay_enabled)
        self._manual_overlay_enabled = bool(self._settings.overlay_enabled)
        self._manual_style_id = self._current_style_id
        self._auto_applied_style_id: str | None = None
        self._active_game_profile_id: str | None = None
        self._auto_profile_settings_backup: tuple[BetaZoomSettings, ReactiveSettings] | None = None
        self._ambiguous_profile_matches: list[str] = []
        self._active_game_profile_misses = 0
        self._last_fullscreen_state = False
        self._fullscreen_true_samples = 0
        self._fullscreen_false_samples = 0
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
        self._input_timer = QTimer(self)
        self._input_timer.setInterval(20)
        self._input_timer.timeout.connect(self._poll_foreground_input)
        self._quick_switch_next_hotkey = parse_hotkey(self._settings.quick_switch_next_hotkey)
        self._quick_switch_previous_hotkey = parse_hotkey(self._settings.quick_switch_previous_hotkey)
        self._quick_switch_favorite_hotkey = parse_hotkey(self._settings.quick_switch_favorite_hotkey)
        self._loadout_hotkey_held = {"next": False, "previous": False, "favorite": False}
        self._sync_input_timer()
        self._zoom_hotkey = parse_hotkey(self._settings.beta_zoom.hotkey_sequence)
        self._zoom_in_hotkey = parse_hotkey(self._settings.beta_zoom.zoom_in_hotkey_sequence)
        self._zoom_out_hotkey = parse_hotkey(self._settings.beta_zoom.zoom_out_hotkey_sequence)
        self._zoom_reset_hotkey = parse_hotkey(self._settings.beta_zoom.zoom_reset_hotkey_sequence)
        self._zoom_adjust_held = {"in": False, "out": False, "reset": False}
        self._zoom_showing = False
        self._wheel_hook = GlobalMouseWheelHook(
            should_handle=lambda: bool(self._zoom_showing and self._settings.beta_zoom.zoom_enabled and self._active_game_profile_id),
            consume_input=lambda: bool(self._settings.beta_zoom.consume_mouse_wheel),
        )
        self._wheel_hook.wheel_delta.connect(self._on_zoom_wheel)
        self._user32_input = ctypes.WinDLL("user32", use_last_error=True)
        self._user32_input.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self._user32_input.GetAsyncKeyState.restype = ctypes.c_short
        self._mouse_left_held = False
        self._mouse_right_held = False
        self._ads_toggle_active = False
        self._ads_active = False
        self._emergency_held = False
        self._emergency_hidden = False
        self._ads_suppressed = False
        self._emergency_hotkey = parse_hotkey(self._settings.reactive.emergency_hotkey)
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
        self._main_window.game_loadouts_updated.connect(self.update_game_loadouts)
        self._main_window.game_loadout_selected.connect(self.select_game_loadout)
        self._main_window.import_game_requested.connect(self.import_manual_game)
        self._main_window.rescan_games_requested.connect(self.rescan_games)
        self._main_window.beta_features_changed.connect(self.set_beta_features_enabled)
        self._main_window.beta_zoom_settings_changed.connect(self.set_beta_zoom_settings)
        self._main_window.accessibility_changed.connect(self.set_accessibility_settings)
        self._main_window.reactive_settings_changed.connect(self.set_reactive_settings)
        self._main_window.loadout_hotkeys_changed.connect(self.set_loadout_hotkeys)
        self._main_window.monitor_offset_changed.connect(self.set_monitor_offset)
        self._main_window.library_metadata_changed.connect(self.set_library_metadata)
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
        self._sync_zoom_timer()
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
        self._emergency_hidden = False
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
            self._settings.recent_style_ids = [style_id, *[item for item in self._settings.recent_style_ids if item != style_id]][:50]
            self._main_window.set_recent_style_ids(self._settings.recent_style_ids)
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
        previous = self._definitions.get(definition.style_id)
        self._definitions[definition.style_id] = definition
        if previous is not None:
            for rgba in (definition.style.color_rgba, definition.style.outline_rgba):
                color = "#{:02X}{:02X}{:02X}".format(*rgba[:3])
                prior = previous.style.color_rgba if rgba == definition.style.color_rgba else previous.style.outline_rgba
                if rgba != prior:
                    self._settings.recent_crosshair_colors = [color, *[c for c in self._settings.recent_crosshair_colors if c != color]][:12]
            self._main_window.set_recent_crosshair_colors(self._settings.recent_crosshair_colors)
            if previous.style != definition.style:
                self._save_settings()
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

    def set_accessibility_settings(self, settings: object) -> None:
        if not isinstance(settings, AccessibilitySettings):
            return
        self._settings.accessibility = settings
        self._main_window.set_accessibility_settings(settings)
        if settings.reduced_motion:
            self._overlay.cancel_fire_pulse()
            self._overlay.set_input_suppressed(False, 0)
            self._ads_suppressed = False
        self._sync_input_timer()
        self._save_settings()

    def set_reactive_settings(self, settings: object) -> None:
        if not isinstance(settings, ReactiveSettings):
            return
        self._settings.reactive = settings
        self._emergency_hotkey = parse_hotkey(settings.emergency_hotkey)
        self._main_window.set_reactive_settings(settings)
        self._sync_input_timer()
        if not settings.enabled:
            self._mouse_left_held = self._mouse_right_held = False
            if self._ads_suppressed:
                self._overlay.set_input_suppressed(False, settings.ads_transition_ms)
                self._ads_suppressed = False
        self._save_settings()

    def set_loadout_hotkeys(self, next_hotkey: str, previous_hotkey: str, favorite_hotkey: str) -> None:
        parsed = tuple(parse_hotkey(value) for value in (next_hotkey, previous_hotkey, favorite_hotkey))
        if any(value is None for value in parsed):
            return
        self._quick_switch_next_hotkey, self._quick_switch_previous_hotkey, self._quick_switch_favorite_hotkey = parsed
        self._settings.quick_switch_next_hotkey = parsed[0].sequence
        self._settings.quick_switch_previous_hotkey = parsed[1].sequence
        self._settings.quick_switch_favorite_hotkey = parsed[2].sequence
        self._main_window.set_quick_switch_hotkeys(*(
            self._settings.quick_switch_next_hotkey,
            self._settings.quick_switch_previous_hotkey,
            self._settings.quick_switch_favorite_hotkey,
        ))
        self._save_settings()

    def set_monitor_offset(self, monitor_id: str, x: int, y: int) -> None:
        if monitor_id not in {key for key, _label in self._monitor_choices()}:
            return
        self._settings.monitor_offsets[monitor_id] = {"x": max(-128, min(128, int(x))), "y": max(-128, min(128, int(y)))}
        self._main_window.set_monitor_offsets(self._settings.monitor_offsets)
        bounds = self._last_overlay_bounds or self._last_game_monitor_bounds
        if bounds is not None and self._overlay_visible and self._monitor_id_for_bounds(bounds) == monitor_id:
            self._overlay.center_on_bounds(bounds[0] + self._settings.monitor_offsets[monitor_id]["x"],
                                           bounds[1] + self._settings.monitor_offsets[monitor_id]["y"],
                                           bounds[2] + self._settings.monitor_offsets[monitor_id]["x"],
                                           bounds[3] + self._settings.monitor_offsets[monitor_id]["y"])
            self._last_overlay_bounds = bounds
        self._save_settings()

    def _monitor_id_for_bounds(self, bounds: tuple[int, int, int, int]) -> str | None:
        left, top, right, bottom = bounds
        center_x, center_y = (left + right) // 2, (top + bottom) // 2
        for index, screen in enumerate(self._app.screens()):
            geometry = screen.geometry()
            if geometry.x() <= center_x < geometry.x() + geometry.width() and geometry.y() <= center_y < geometry.y() + geometry.height():
                return f"screen:{index}"
        return None

    def _sync_input_timer(self) -> None:
        reactive_input = self._settings.reactive.enabled and not self._settings.accessibility.reduced_motion
        should_run = bool(reactive_input or self._active_game_profile_id)
        if should_run and not self._input_timer.isActive():
            self._input_timer.start()
        elif not should_run and self._input_timer.isActive():
            self._input_timer.stop()
            self._loadout_hotkey_held = {"next": False, "previous": False, "favorite": False}

    def _poll_quick_switch_hotkeys(self, game_foreground: bool) -> None:
        checks = (
            ("next", self._quick_switch_next_hotkey, lambda: self._cycle_game_loadout(1)),
            ("previous", self._quick_switch_previous_hotkey, lambda: self._cycle_game_loadout(-1)),
            ("favorite", self._quick_switch_favorite_hotkey, self._cycle_favorite_style),
        )
        for key, spec, action in checks:
            down = bool(game_foreground and is_hotkey_pressed(spec))
            if down and not self._loadout_hotkey_held[key]:
                action()
            self._loadout_hotkey_held[key] = down

    def _cycle_game_loadout(self, step: int) -> None:
        profile = self._profile_for_game(self._active_game_profile_id or "")
        if profile is None or len(profile.loadouts) < 2:
            return
        index = next((i for i, item in enumerate(profile.loadouts) if item.loadout_id == profile.active_loadout_id), 0)
        target = profile.loadouts[(index + step) % len(profile.loadouts)]
        self.select_game_loadout(profile.game_id, target.loadout_id)

    def _cycle_favorite_style(self) -> None:
        favorites = [style_id for style_id in self._settings.favorite_style_ids if style_id in self._definitions]
        if not favorites:
            return
        try:
            index = favorites.index(self._current_style_id)
        except ValueError:
            index = -1
        self.set_overlay_style(favorites[(index + 1) % len(favorites)], persist=True)

    def _poll_foreground_input(self) -> None:
        reactive = self._settings.reactive
        if self._is_quitting:
            return
        try:
            game_foreground = bool(self._active_game_profile_id) and is_foreground_fullscreen()
        except Exception:
            game_foreground = False
        self._poll_quick_switch_hotkeys(bool(game_foreground))
        emergency_down = game_foreground and is_hotkey_pressed(self._emergency_hotkey)
        if emergency_down and not self._emergency_held:
            self._emergency_hidden = not self._emergency_hidden
            if self._emergency_hidden:
                self.hide_overlay()
            else:
                self.show_overlay()
        self._emergency_held = emergency_down
        if not game_foreground:
            self._mouse_left_held = self._mouse_right_held = False
            self._ads_toggle_active = False
            self._set_ads_state(False)
            self._overlay.cancel_fire_pulse()
            return
        left = bool(self._user32_input.GetAsyncKeyState(0x01) & 0x8000)
        right = bool(self._user32_input.GetAsyncKeyState(0x02) & 0x8000)
        if reactive.enabled and not self._settings.accessibility.reduced_motion and left and not self._mouse_left_held and reactive.fire_pulse and self._overlay_visible and not self._emergency_hidden:
            self._overlay.trigger_fire_pulse(
                reactive.fire_duration_ms,
                reactive.fire_amplitude_percent if reactive.gap_expansion else 0,
                reactive.opacity_pulse,
                reactive.gap_expansion,
            )
        profile = self._profile_for_game(self._active_game_profile_id or "")
        loadout = self._selected_game_loadout(profile) if profile else None
        self._ads_toggle_active, ads_active = _next_ads_state(
            reactive.ads_mode, right, self._mouse_right_held, self._ads_toggle_active
        )
        self._set_ads_state(ads_active)
        should_hide = bool((reactive.hide_on_ads or (loadout.hide_on_ads if loadout else False)) and ads_active)
        if should_hide != self._ads_suppressed:
            transition = 0 if self._settings.accessibility.reduced_motion else (loadout.ads_transition_ms if loadout else reactive.ads_transition_ms)
            self._overlay.set_input_suppressed(should_hide, transition)
            self._ads_suppressed = should_hide
        self._mouse_left_held = left
        self._mouse_right_held = right

    def _set_ads_state(self, active: bool) -> None:
        if self._ads_active == bool(active):
            return
        self._ads_active = bool(active)
        self._overlay.set_style(self._effective_style())
        if not active and self._ads_suppressed:
            self._overlay.set_input_suppressed(False, 0 if self._settings.accessibility.reduced_motion else self._settings.reactive.ads_transition_ms)
            self._ads_suppressed = False

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
        self._sync_zoom_timer()
        self._save_settings()

    def set_beta_zoom_settings(self, settings: object) -> None:
        if not isinstance(settings, BetaZoomSettings):
            return
        previous_settings = self._settings.beta_zoom
        normalized = self._normalized_beta_zoom_settings(settings)
        if previous_settings.auto_adapt_enabled != normalized.auto_adapt_enabled:
            status = (
                "Waiting for GPU telemetry; selected runtime mode remains the baseline."
                if normalized.auto_adapt_enabled else
                "Automatic adaptation is off; the selected mode is locked."
            )
            self._gpu_runtime_adaptation.reset(status)
        elif previous_settings.runtime_mode != normalized.runtime_mode:
            status = (
                "Selected runtime mode changed; GPU adaptation sampling restarted."
                if normalized.auto_adapt_enabled else
                "Automatic adaptation is off; the selected mode is locked."
            )
            self._gpu_runtime_adaptation.reset(status)
        self._settings.beta_zoom = normalized
        self._zoom_hotkey = parse_hotkey(normalized.hotkey_sequence)
        self._zoom_in_hotkey = parse_hotkey(normalized.zoom_in_hotkey_sequence)
        self._zoom_out_hotkey = parse_hotkey(normalized.zoom_out_hotkey_sequence)
        self._zoom_reset_hotkey = parse_hotkey(normalized.zoom_reset_hotkey_sequence)
        self._main_window.set_beta_zoom_settings(normalized)
        if not normalized.zoom_enabled and not normalized.live_enabled:
            self._hide_zoom_overlay()
        self._zoom_generation += 1
        self._zoom_processor.set_generation(self._zoom_generation)
        self._sync_zoom_timer()
        self._save_settings()

    def import_pack(self, pack_path: str) -> None:
        try:
            source = Path(pack_path)
            suffix = source.suffix.lower()
            creator_model = None
            if suffix == XHAIR_EXTENSION:
                definitions = [load_xhair(source)]
            elif suffix == XPACK_EXTENSION:
                definitions = load_xpack(source)
            elif suffix == ".chgrid":
                creator_model = load_creator_crosshair(source)
                definitions = [CrosshairDefinition(
                    style=creator_to_overlay_style(creator_model), family="Creator",
                    description="Imported creator design.", tags=("creator", "imported"),
                    editable_settings=self._definitions[default_style_id()].editable_settings,
                    source_type="creator_grid",
                )]
            else:
                style = load_style_pack(source)
                definitions = [CrosshairDefinition(
                    style=style, family="Legacy Pack", description="Imported from legacy .chpack.",
                    tags=("legacy", "pack"),
                    editable_settings=self._definitions[default_style_id()].editable_settings,
                    source_type="legacy_pack",
                )]

            conflicts = self._find_import_conflicts(definitions, self._definitions)
            strategy = "duplicate"
            replace_targets = [self._matching_import_conflict(item, self._definitions) for item in conflicts]
            replaceable_targets = [item for item in replace_targets if item is not None and self._is_replaceable_import_conflict(item)]
            can_replace = (
                bool(conflicts)
                and len(replaceable_targets) == len(conflicts)
                and len({item.style_id for item in replaceable_targets}) == len(conflicts)
            )
            if conflicts:
                names = "\n".join(f"• {item.display_name} ({item.style_id})" for item in conflicts[:12])
                if len(conflicts) > 12:
                    names += f"\n• and {len(conflicts) - 12} more"
                box = QMessageBox(self._main_window)
                box.setWindowTitle("Import conflict preview")
                box.setIcon(QMessageBox.Icon.Warning)
                box.setText(f"{len(definitions)} style(s) are ready to import. {len(conflicts)} conflict with existing IDs or names.")
                box.setInformativeText(f"Conflicts:\n{names}\n\nReplace is available only for user-created .xhair files; each replaced file is backed up first.")
                duplicate_button = box.addButton("Import as copies", QMessageBox.ButtonRole.AcceptRole)
                skip_button = box.addButton("Keep existing", QMessageBox.ButtonRole.ActionRole)
                replace_button = box.addButton("Replace with backup", QMessageBox.ButtonRole.DestructiveRole)
                replace_button.setEnabled(can_replace)
                box.addButton(QMessageBox.StandardButton.Cancel)
                box.setDefaultButton(duplicate_button)
                box.exec()
                clicked = box.clickedButton()
                if clicked == duplicate_button:
                    strategy = "duplicate"
                elif clicked == skip_button:
                    strategy = "skip"
                elif clicked == replace_button and can_replace:
                    strategy = "replace"
                else:
                    return
            skipped_ids: list[str] = []
            if strategy == "skip" and conflicts:
                conflict_keys = {(item.style_id, item.display_name.strip().casefold()) for item in conflicts}
                skipped_ids = [item.style_id for item in conflicts]
                definitions = [item for item in definitions if (item.style_id, item.display_name.strip().casefold()) not in conflict_keys]
                if not definitions:
                    QMessageBox.information(self._main_window, "Nothing Imported", "Every style matched an existing ID or name. No files were changed.")
                    return

            bundle_dir = self._storage_paths.create_import_bundle(source.stem)
            items_dir = bundle_dir / "items"
            saved_ids: list[str] = []

            if strategy == "replace" and conflicts:
                shutil.copy2(source, bundle_dir / source.name)
                backup_dir = bundle_dir / "replaced"
                backup_dir.mkdir(parents=True, exist_ok=True)
                for incoming in definitions:
                    existing = self._matching_import_conflict(incoming, self._definitions)
                    if existing is not None:
                        if not self._is_replaceable_import_conflict(existing):
                            raise ValueError(f"Cannot safely replace {existing.display_name}; it is not a user-created .xhair file.")
                        destination = Path(existing.source_path)
                        shutil.copy2(destination, backup_dir / destination.name)
                        replacement_style = style_with_updates(incoming.style, {
                            "style_id": existing.style_id,
                            "display_name": existing.display_name,
                        })
                        replacement = replace(
                            incoming, style=replacement_style, source_type="custom",
                            source_path=str(destination), is_favorite=existing.is_favorite,
                        )
                        self._write_xhair_atomically(replacement, destination)
                        saved_ids.append(existing.style_id)
                    else:
                        stored = self._store_imported_definition(incoming, items_dir, source_type="imported_pack")
                        saved_ids.append(stored.style_id)

            if strategy != "replace" and suffix in {XHAIR_EXTENSION, XPACK_EXTENSION, ".chpack"}:
                for definition in definitions:
                    source_type = "legacy_pack" if suffix == ".chpack" else "imported_pack"
                    stored = self._store_imported_definition(definition, items_dir, source_type=source_type)
                    saved_ids.append(stored.style_id)
                shutil.copy2(source, bundle_dir / source.name)
            elif strategy != "replace" and suffix == ".chgrid":
                assert creator_model is not None
                target_id = self._next_available_style_id(self._slugify(creator_model.style_id or creator_model.name), items_dir, ".chgrid")
                creator_model.style_id = target_id
                target = items_dir / f"{target_id}.chgrid"
                save_creator_crosshair(creator_model, target)
                saved_ids.append(target_id)

            manifest = {
                "imported_at": datetime.now().isoformat(timespec="seconds"),
                "source_name": source.name,
                "source_suffix": suffix,
                "imported_style_ids": saved_ids,
                "conflict_strategy": strategy,
                "skipped_conflict_ids": skipped_ids,
            }
            (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            self._definitions = self._library.load(self._storage_paths.root)
            self._hydrate_favorites()
            selected = saved_ids[-1] if saved_ids else self._current_style_id
            self._main_window.refresh_definitions(self._definitions, selected_style_id=selected)
            self.set_overlay_style(selected)
            self._refresh_games_page()
            QMessageBox.information(
                self._main_window,
                "Import Complete",
                f"Imported {len(saved_ids)} crosshair(s) into:\n{bundle_dir}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Import Failed", f"Could not import crosshair file.\n{exc}")

    def export_current_style(self, destination: str) -> None:
        try:
            definition = self._definitions[self._current_style_id]
            save_xhair(definition, Path(destination))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Export Failed", f"Could not export crosshair.\n{exc}")

    @staticmethod
    def _find_import_conflicts(definitions: list[CrosshairDefinition],
                               existing: dict[str, CrosshairDefinition]) -> list[CrosshairDefinition]:
        existing_names = {item.display_name.strip().casefold() for item in existing.values()}
        return [item for item in definitions
                if item.style_id in existing or item.display_name.strip().casefold() in existing_names]

    def _matching_import_conflict(self, incoming: CrosshairDefinition,
                                  existing: dict[str, CrosshairDefinition]) -> CrosshairDefinition | None:
        by_id = existing.get(incoming.style_id)
        if by_id is not None:
            return by_id
        folded_name = incoming.display_name.strip().casefold()
        return next((item for item in existing.values() if item.display_name.strip().casefold() == folded_name), None)

    def _is_replaceable_import_conflict(self, definition: CrosshairDefinition) -> bool:
        if definition.source_type != "custom" or not definition.source_path:
            return False
        source = Path(definition.source_path)
        try:
            source.resolve().relative_to(self._storage_paths.custom_dir.resolve())
        except (OSError, ValueError):
            return False
        return source.suffix.casefold() == XHAIR_EXTENSION and source.is_file()

    @staticmethod
    def _write_xhair_atomically(definition: CrosshairDefinition, destination: Path) -> None:
        temporary = destination.with_name(destination.name + ".import.tmp")
        try:
            save_xhair(definition, temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def export_style_definition(self, style_id: str, destination: str) -> None:
        try:
            if style_id not in self._definitions:
                return
            save_xhair(self._definitions[style_id], Path(destination))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Export Failed", f"Could not export crosshair.\n{exc}")

    def export_selected_pack(self, style_ids: list[object], destination: str) -> None:
        resolved_ids = [str(style_id) for style_id in style_ids if str(style_id) in self._definitions]
        if not resolved_ids:
            return
        definitions = self._library.definitions_for_ids(resolved_ids)
        metadata = {
            "pack_name": Path(destination).stem,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "count": len(definitions),
        }
        try:
            save_xpack(definitions, Path(destination), metadata=metadata)
            QMessageBox.information(
                self._main_window,
                "Pack Exported",
                f"Exported {len(definitions)} crosshair(s) to:\n{destination}",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Export Failed", f"Could not export crosshair pack.\n{exc}")

    def reset_settings(self) -> None:
        preview = QMessageBox(self._main_window)
        preview.setWindowTitle("Preview settings reset")
        preview.setIcon(QMessageBox.Icon.Question)
        preview.setText("Reset application settings to their defaults?")
        preview.setInformativeText(
            "This resets appearance, overlay size and visibility, game/loadout assignments, "
            "hotkeys, Zoom, accessibility, favorites, collections, and recent items. "
            "Your crosshair files are kept. The current valid settings file is backed up before reset."
        )
        reset_button = preview.addButton("Back up and reset", QMessageBox.ButtonRole.DestructiveRole)
        preview.addButton(QMessageBox.StandardButton.Cancel)
        preview.setDefaultButton(QMessageBox.StandardButton.Cancel)
        preview.exec()
        if preview.clickedButton() != reset_button:
            return
        self._config.backup_current_settings()
        self._settings = AppSettings(
            crosshair_storage_path=self._settings.crosshair_storage_path or str(self._config.default_crosshair_path)
        )
        self._definitions = self._library.load(Path(self._settings.crosshair_storage_path))
        self._current_style_id = self._validated_style_id(self._settings.selected_style_id)
        self._manual_style_id = self._current_style_id
        self._auto_applied_style_id = None
        self._active_game_profile_id = None
        self._zoom_hotkey = parse_hotkey(self._settings.beta_zoom.hotkey_sequence)
        self._zoom_showing = False
        self._last_game_monitor_bounds = None
        self._last_game_window_bounds = None
        self._overlay.set_style(self._effective_style())
        self._hide_zoom_overlay()
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id)
        self._main_window.set_selected_style(self._current_style_id)
        self._main_window.set_selected_style_name(self._definitions[self._current_style_id].display_name)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._main_window.set_selected_size(self._settings.selected_size_percent)
        self._main_window.set_global_size(self._settings.global_size_percent)
        self._main_window.set_theme_values(self._settings.theme_mode, self._settings.accent_color, self._theme_manager.resolved_mode.value)
        self._main_window.set_beta_page_visible(self._settings.beta_zoom.sidebar_enabled)
        self._main_window.set_beta_zoom_settings(self._settings.beta_zoom)
        self._refresh_beta_monitor_choices()
        self._apply_theme()
        if self._settings.overlay_enabled:
            self._overlay.show()
            self._overlay_visible = True
            self._manual_overlay_enabled = True
            self._main_window.set_overlay_status(True)
        else:
            self._overlay.hide()
            self._overlay_visible = False
            self._manual_overlay_enabled = False
            self._main_window.set_overlay_status(False)
        self._reload_games()
        self._refresh_games_page()
        self._sync_windows_autostart_setting()
        self._save_settings()

    def _check_updates_on_startup(self) -> None:
        if not self._settings.auto_update_on_startup:
            return
        if self._update_check_running:
            return
        self._update_check_running = True
        worker = _ReleaseCheckWorker(self._update_manager)
        worker.signals.finished.connect(self._handle_startup_update_result)
        self._start_worker(worker)

    def _handle_startup_update_result(self, result: object) -> None:
        self._update_check_running = False
        if isinstance(result, Exception) or not isinstance(result, ReleaseInfo):
            self._main_window.set_update_available(False)
            return
        release = result
        update_available = self._update_manager.is_newer_than_current(release) and release.installer_asset is not None
        self._main_window.set_update_available(update_available)
        if not update_available:
            return
        if not self._settings.auto_update_on_startup:
            return
        if not self._update_manager.can_self_update():
            return
        if self._confirm_update_install(release):
            self._download_and_install_update(release)

    def _sync_windows_autostart_setting(self) -> None:
        if winreg is None or os.name != "nt":
            return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "CCCrosshairOverlay"
        command = self._startup_command()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if self._settings.run_on_startup_tray and command:
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, value_name)
                    except OSError:
                        pass
        except OSError:
            pass

    def _startup_command(self) -> str:
        if getattr(sys, "frozen", False):
            exe = Path(sys.executable).resolve()
            return f'"{exe}" --tray-start'
        pythonw = Path(sys.executable).resolve()
        main_file = Path(__file__).resolve().parents[2] / "main.py"
        if not main_file.exists():
            return ""
        return f'"{pythonw}" "{main_file}" --tray-start'

    def check_for_updates(self, silent_if_latest: bool = False, silent_on_error: bool = False) -> None:
        if self._update_check_running:
            return
        self._update_check_running = True
        self._manual_update_options = (silent_if_latest, silent_on_error)
        self._manual_update_progress = self._indefinite_progress_dialog("Checking GitHub releases...")
        worker = _ReleaseCheckWorker(self._update_manager, timeout_s=8.0)
        worker.signals.finished.connect(self._handle_manual_update_result)
        self._start_worker(worker)

    def _handle_manual_update_result(self, result: object) -> None:
        self._update_check_running = False
        if self._manual_update_progress is not None:
            self._manual_update_progress.close()
            self._manual_update_progress = None
        silent_if_latest, silent_on_error = self._manual_update_options
        if isinstance(result, Exception):
            if not silent_on_error:
                QMessageBox.warning(self._main_window, "Updates", str(result))
            return
        if not isinstance(result, ReleaseInfo):
            return
        release = result

        if not self._update_manager.is_newer_than_current(release):
            self._main_window.set_update_available(False)
            if not silent_if_latest:
                QMessageBox.information(
                    self._main_window,
                    "Updates",
                    f"You're up to date.\nCurrent version: {APP_VERSION}",
                )
            return

        if release.installer_asset is None:
            self._main_window.set_update_available(False)
            QMessageBox.warning(
                self._main_window,
                "Updates",
                "A newer GitHub release was found, but it does not contain a Windows installer asset yet.",
            )
            return

        self._main_window.set_update_available(True)

        if not self._update_manager.can_self_update():
            QMessageBox.information(
                self._main_window,
                "Update Available",
                (
                    f"Version {release.version} is available on GitHub.\n\n"
                    "Automatic in-place updates work from the installed app build.\n"
                    f"Release page:\n{release.html_url}"
                ),
            )
            return

        if not self._confirm_update_install(release):
            return
        self._download_and_install_update(release)

    def _confirm_update_install(self, release: ReleaseInfo) -> bool:
        published = release.published_at or "unknown date"
        answer = QMessageBox.question(
            self._main_window,
            "Install Update",
            (
                f"A new version is available.\n\n"
                f"Current version: {APP_VERSION}\n"
                f"Latest version: {release.version}\n"
                f"Published: {published}\n\n"
                "The installer will be downloaded, this app will close, the update will install silently, "
                "and then the app will relaunch automatically.\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _download_and_install_update(self, release: ReleaseInfo) -> None:
        progress = QProgressDialog("Downloading update...", None, 0, 0, self._main_window)
        progress.setWindowTitle("Updating")
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        self._download_progress = progress
        worker = _DownloadUpdateWorker(self._update_manager, release)
        worker.signals.progress.connect(self._handle_update_progress)
        worker.signals.finished.connect(self._handle_update_download_result)
        self._start_worker(worker)

    def _handle_update_progress(self, downloaded: int, total: int) -> None:
        if self._download_progress is not None:
            self._update_progress(self._download_progress, downloaded, total)

    def _handle_update_download_result(self, result: object) -> None:
        if self._download_progress is not None:
            self._download_progress.close()
            self._download_progress = None
        if isinstance(result, Exception):
            QMessageBox.warning(self._main_window, "Update Failed", str(result))
            return
        QMessageBox.information(
            self._main_window,
            "Installing Update",
            "The update was downloaded. Crosshair Overlay will now close, install the new version, and relaunch.",
        )
        self.quit_application()

    def _update_progress(self, dialog: QProgressDialog, downloaded: int, total: int) -> None:
        if total > 0:
            dialog.setRange(0, total)
            dialog.setValue(min(downloaded, total))
            dialog.setLabelText(f"Downloading update... {downloaded // 1024} KB / {max(1, total // 1024)} KB")
        else:
            dialog.setRange(0, 0)
            dialog.setLabelText("Downloading update...")
        QApplication.processEvents()

    def _indefinite_progress_dialog(self, label: str) -> QProgressDialog:
        dialog = QProgressDialog(label, None, 0, 0, self._main_window)
        dialog.setWindowTitle("Updates")
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setMinimumDuration(0)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setCancelButton(None)
        dialog.show()
        QApplication.processEvents()
        return dialog

    def save_creator_crosshair(self, model: object, activate_now: bool) -> None:
        if not isinstance(model, CreatorCrosshair):
            return
        try:
            style = creator_to_overlay_style(model)
            style_id = self._creator_style_id(model, style.display_name)
            style = style_with_updates(style, {"style_id": style_id})
            creator_model = CreatorCrosshair(
                name=model.name,
                grid_size=model.grid_size,
                creation_mode=model.creation_mode,
                color_hex=model.color_hex,
                filled_cells=model.normalized_cells(),
                style_id=style.style_id,
                created_at=model.created_at,
                updated_at=model.updated_at,
                layers=[CreatorLayer(layer.layer_id, layer.name, layer.primitive, layer.visible, list(layer.filled_cells)) for layer in model.layers],
            )
            destination = self._storage_paths.creator_definition_path(style.style_id)
            save_creator_crosshair(creator_model, destination)

            self._definitions = self._library.load(self._storage_paths.root)
            self._hydrate_favorites()

            self._main_window.refresh_definitions(self._definitions, selected_style_id=style.style_id)
            self._main_window.set_creator_model(creator_model)
            if activate_now:
                self.set_overlay_style(style.style_id)
            self._refresh_games_page()
            QMessageBox.information(self._main_window, "Saved", f"Saved creator crosshair '{style.display_name}'.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Save Failed", f"Could not save creator crosshair.\n{exc}")

    def export_creator_crosshair(self, model: object, destination: str) -> None:
        if not isinstance(model, CreatorCrosshair):
            return
        try:
            save_creator_crosshair(model, Path(destination))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._main_window, "Export Failed", f"Could not export creator crosshair.\n{exc}")

    def send_style_to_editor(self, style_id: str) -> None:
        if style_id not in self._definitions:
            return
        definition = self._definitions[style_id]
        model: CreatorCrosshair | None = None

        if definition.source_type == "creator_grid" and definition.source_path:
            source = Path(definition.source_path)
            if source.exists():
                try:
                    model = load_creator_crosshair(source)
                except Exception:  # noqa: BLE001
                    model = None

        if model is None and definition.style.shape == OverlayShape.CUSTOM_GRID:
            color_hex = "#{:02X}{:02X}{:02X}".format(
                definition.style.color_rgba[0],
                definition.style.color_rgba[1],
                definition.style.color_rgba[2],
            )
            model = CreatorCrosshair(
                name=definition.display_name,
                grid_size=max(16, min(64, int(definition.style.custom_grid_size))),
                creation_mode="pixel",
                color_hex=color_hex,
                filled_cells=[(int(x), int(y)) for x, y in definition.style.custom_filled_cells],
                style_id=definition.style_id,
            )

        if model is None:
            model = overlay_style_to_creator(model_name=definition.display_name, style=definition.style, grid_size=32)

        self._main_window.open_creator_with_model(model)

    def _store_imported_definition(self, definition: CrosshairDefinition, items_dir: Path, source_type: str) -> CrosshairDefinition:
        items_dir.mkdir(parents=True, exist_ok=True)
        target_id = self._next_available_style_id(self._slugify(definition.display_name or definition.style_id), items_dir, ".xhair")
        style = style_with_updates(definition.style, {"style_id": target_id, "display_name": definition.display_name})
        stored = CrosshairDefinition(
            style=style,
            family=definition.family,
            description=definition.description,
            tags=definition.tags,
            editable_settings=definition.editable_settings,
            source_type=source_type,
            source_path=str(items_dir / f"{target_id}.xhair"),
            is_favorite=definition.is_favorite,
            aliases=definition.aliases,
            origin_game=definition.origin_game,
            author=definition.author,
            source_url=definition.source_url,
            reuse_status=definition.reuse_status,
            approximate=definition.approximate,
            catalog_version=definition.catalog_version,
        )
        destination = items_dir / f"{target_id}.xhair"
        save_xhair(stored, destination)
        return stored

    def _creator_style_id(self, model: CreatorCrosshair, display_name: str) -> str:
        existing = self._definitions.get(model.style_id)
        if existing is not None and existing.source_type == "creator_grid":
            return model.style_id
        return self._next_available_style_id(
            self._slugify(display_name), self._storage_paths.creator_dir, ".chgrid"
        )

    def _next_available_style_id(self, base_id: str, directory: Path, suffix: str) -> str:
        existing_ids = set(self._definitions.keys())
        target_id = base_id
        index = 2
        while target_id in existing_ids or (directory / f"{target_id}{suffix}").exists():
            target_id = f"{base_id}_{index}"
            index += 1
        return target_id

    def set_auto_enable_on_fullscreen(self, enabled: bool) -> None:
        self._settings.auto_enable_on_fullscreen = bool(enabled)
        if not enabled:
            self._set_overlay_visible(self._manual_overlay_enabled, persist=False)
        self._refresh_games_page()
        self._save_settings()

    def set_auto_switch_game_profiles(self, enabled: bool) -> None:
        self._settings.auto_switch_game_profiles = bool(enabled)
        if not enabled and self._auto_applied_style_id is not None:
            self._set_ads_state(False)
            self._active_game_profile_id = None
            self._restore_manual_style_if_needed()
            self._overlay.set_style(self._effective_style())
            self._restore_auto_profile_settings()
        self._refresh_games_page()
        self._save_settings()

    def update_game_profile(self, game_id: str, style_id: str, enabled: bool) -> None:
        game_map = {game.game_id: game for game in self._all_games()}
        discovered = game_map.get(game_id)
        profile = self._profile_for_game(game_id)
        if profile is None:
            profile = GameProfile(
                game_id=game_id,
                title=discovered.title if discovered else game_id,
                source=discovered.source if discovered else "manual",
                executable_names=[],
                executable_path="",
                icon_path="",
                style_id="",
                enabled=False,
            )
            self._settings.game_profiles.append(profile)

        if discovered is not None:
            profile.title = discovered.title
            profile.source = discovered.source
            profile.executable_path = discovered.executable_path
            profile.icon_path = discovered.icon_path
            executable_name = discovered.executable_name.strip().lower()
            profile.executable_names = [executable_name] if executable_name else []

        profile.style_id = style_id if style_id in self._definitions else ""
        if not profile.style_id:
            profile.loadouts = []
            profile.active_loadout_id = ""
        elif not profile.loadouts:
            profile.loadouts = [GameLoadout("default", "Default", profile.style_id)]
            profile.active_loadout_id = "default"
        elif profile.loadouts:
            active_loadout = next((item for item in profile.loadouts if item.loadout_id == profile.active_loadout_id), profile.loadouts[0])
            active_loadout.style_id = profile.style_id
            profile.active_loadout_id = active_loadout.loadout_id
        profile.enabled = bool(enabled and profile.style_id)
        self._refresh_games_page()
        self._save_settings()

    def update_game_loadouts(self, game_id: str, loadouts: object, active_loadout_id: str) -> None:
        if not isinstance(loadouts, list) or any(not isinstance(item, dict) for item in loadouts):
            return
        profile = self._profile_for_game(game_id)
        if profile is None:
            discovered = next((item for item in self._all_games() if item.game_id == game_id), None)
            if discovered is None:
                return
            profile = GameProfile(game_id, discovered.title, discovered.source,
                                  executable_names=[discovered.executable_name] if discovered.executable_name else [],
                                  executable_path=discovered.executable_path, icon_path=discovered.icon_path)
            self._settings.game_profiles.append(profile)
        profile.loadouts = [GameLoadout(**item) for item in loadouts]
        active = next((item for item in profile.loadouts if item.loadout_id == active_loadout_id), None)
        profile.active_loadout_id = active.loadout_id if active else ""
        profile.style_id = active.style_id if active else ""
        profile.enabled = bool(profile.enabled and profile.style_id)
        if self._active_game_profile_id == game_id and active:
            self._apply_game_loadout(profile, active)
            self._auto_applied_style_id = active.style_id
        self._refresh_games_page()
        self._save_settings()

    def select_game_loadout(self, game_id: str, loadout_id: str) -> None:
        profile = self._profile_for_game(game_id)
        if profile is None:
            return
        loadout = next((item for item in profile.loadouts if item.loadout_id == loadout_id), None)
        if loadout is None:
            return
        profile.active_loadout_id = loadout.loadout_id
        profile.style_id = loadout.style_id
        if self._settings.auto_switch_game_profiles and self._active_game_profile_id == game_id:
            self._apply_game_loadout(profile, loadout)
            self._auto_applied_style_id = loadout.style_id
        self._refresh_games_page()
        self._save_settings()

    def _apply_game_loadout(self, profile: GameProfile, loadout: GameLoadout) -> None:
        if self._auto_profile_settings_backup is None:
            self._auto_profile_settings_backup = (replace(self._settings.beta_zoom), replace(self._settings.reactive))
        self.set_overlay_style(loadout.style_id, persist=False)
        self.set_beta_zoom_settings(replace(self._settings.beta_zoom, zoom_percent=loadout.zoom_percent))
        self.set_reactive_settings(replace(
            self._settings.reactive,
            fire_pulse=loadout.fire_pulse,
            gap_expansion=loadout.gap_expansion,
            opacity_pulse=loadout.opacity_pulse,
            hide_on_ads=loadout.hide_on_ads,
            fire_duration_ms=loadout.fire_duration_ms,
            fire_amplitude_percent=loadout.fire_amplitude_percent,
            ads_transition_ms=loadout.ads_transition_ms,
        ))

    def _restore_auto_profile_settings(self) -> None:
        backup, self._auto_profile_settings_backup = self._auto_profile_settings_backup, None
        if backup is None:
            return
        zoom, reactive = backup
        self.set_beta_zoom_settings(zoom)
        self.set_reactive_settings(reactive)

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
                    loadouts=[asdict(item) for item in profile.loadouts] if profile else [],
                    active_loadout_id=profile.active_loadout_id if profile else "",
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

        fullscreen = self._debounce_fullscreen_state(fullscreen)
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

        active_profile = self._stable_active_game_profile(self._resolve_active_game_profile(running_names))
        if monitor_bounds is not None and fullscreen:
            self._last_game_monitor_bounds = monitor_bounds
        if window_bounds is not None and fullscreen:
            self._last_game_window_bounds = window_bounds

        should_show_overlay = self._manual_overlay_enabled
        if self._settings.auto_enable_on_fullscreen:
            should_show_overlay = fullscreen
        if self._emergency_hidden:
            should_show_overlay = False
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
                monitor_id = self._monitor_id_for_bounds(overlay_bounds)
                offset = self._settings.monitor_offsets.get(monitor_id or "", {})
                self._overlay.center_on_bounds(
                    overlay_bounds[0] + offset.get("x", 0), overlay_bounds[1] + offset.get("y", 0),
                    overlay_bounds[2] + offset.get("x", 0), overlay_bounds[3] + offset.get("y", 0),
                )
                self._last_overlay_bounds = overlay_bounds

        if self._settings.auto_switch_game_profiles and active_profile is not None:
            active_loadout = self._selected_game_loadout(active_profile)
            active_style_id = active_loadout.style_id if active_loadout else active_profile.style_id
            if active_style_id in self._definitions and self._active_game_profile_id != active_profile.game_id:
                self._active_game_profile_id = active_profile.game_id
                self._auto_applied_style_id = active_style_id
                if active_loadout:
                    self._apply_game_loadout(active_profile, active_loadout)
                else:
                    self.set_overlay_style(active_style_id, persist=False)
        else:
            self._set_ads_state(False)
            self._active_game_profile_id = None
            self._restore_manual_style_if_needed()
            self._overlay.set_style(self._effective_style())
            self._restore_auto_profile_settings()
            self._active_game_profile_misses = 0

        runtime_status = self._current_runtime_status()
        if runtime_status != self._last_runtime_status:
            self._main_window.set_games_status(runtime_status)
            self._last_runtime_status = runtime_status
        self._sync_input_timer()

    def _zoom_tick(self) -> None:
        live_zoom_enabled = self._settings.beta_zoom.sidebar_enabled and self._settings.beta_zoom.live_enabled
        allow_zoom = self._settings.beta_zoom.sidebar_enabled and self._settings.beta_zoom.zoom_enabled
        if allow_zoom and (live_zoom_enabled or getattr(self, "_zoom_capture_active", False)):
            self._poll_zoom_adjustment_hotkeys()
        hotkey_down = allow_zoom and is_hotkey_pressed(self._zoom_hotkey)
        if not live_zoom_enabled and not hotkey_down:
            self._hide_zoom_overlay()
            return
        self._zoom_capture_active = True

        source_frame = self._current_zoom_source_frame()
        source_screen = self._screen_for_frame(source_frame)
        if source_screen is None:
            self._hide_zoom_overlay()
            return

        target_screen = self._target_zoom_screen(source_screen, source_frame)
        if target_screen is None:
            self._hide_zoom_overlay()
            return

        capture_point = self._current_zoom_capture_point(source_screen, source_frame)
        target_rect = self._zoom_target_rect(target_screen, capture_point)
        if target_rect is None:
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
        if pixmap is None or pixmap.isNull():
            self._hide_zoom_overlay()
            return

        if not live_zoom_enabled and not hotkey_down:
            self._hide_zoom_overlay()
            return

        self._zoom_target_rect_current = target_rect
        self._zoom_processor.submit(
            pixmap.toImage(),
            (max(1, target_rect.width() - 20), max(1, target_rect.height() - 20)),
            self._zoom_generation,
            self._gpu_runtime_adaptation.effective_mode(self._settings.beta_zoom.runtime_mode),
            cleanup_enabled=bool(self._settings.beta_zoom.cleanup_enabled and self._active_game_profile_id),
            cleanup_radius=self._settings.beta_zoom.cleanup_radius,
            cleanup_strength=self._settings.beta_zoom.cleanup_strength,
            cleanup_preview=self._settings.beta_zoom.cleanup_preview,
        )

    def _on_zoom_frame(self, image, generation: int, captured_at: float, dropped_frames: int) -> None:
        del captured_at, dropped_frames
        if generation != self._zoom_generation or not self._zoom_capture_active or image.isNull():
            return
        target_rect = self._zoom_target_rect_current
        if target_rect is None:
            return
        animate = bool(
            self._settings.beta_zoom.animation_enabled
            and not self._settings.accessibility.reduced_motion
            and not self._zoom_showing
        )
        self._zoom_overlay.show_zoom(
            pixmap=QPixmap.fromImage(image),
            target_rect=target_rect,
            animate=animate,
            duration_ms=self._settings.beta_zoom.animation_duration_ms,
        )
        self._zoom_showing = True
        now = time.monotonic()
        if now - self._last_zoom_diagnostics_publish >= 1.0:
            self._last_zoom_diagnostics_publish = now
            diagnostics = self._zoom_processor.diagnostics
            diagnostics["effectiveZoomMax"] = self._zoom_effective_max_percent
            diagnostics["adaptation"] = self._gpu_runtime_adaptation.status
            self._main_window.set_zoom_diagnostics(diagnostics)

    def _poll_zoom_adjustment_hotkeys(self) -> None:
        settings = self._settings.beta_zoom
        checks = (
            ("in", self._zoom_in_hotkey, min(1600, settings.zoom_percent + 100)),
            ("out", self._zoom_out_hotkey, max(200, settings.zoom_percent - 100)),
            ("reset", self._zoom_reset_hotkey, 200),
        )
        next_percent = settings.zoom_percent
        for name, spec, target in checks:
            held = is_hotkey_pressed(spec)
            if held and not self._zoom_adjust_held[name]:
                next_percent = target
            self._zoom_adjust_held[name] = held
        if next_percent != settings.zoom_percent:
            self.set_beta_zoom_settings(replace(settings, zoom_percent=next_percent))

    def _on_zoom_wheel(self, delta: int) -> None:
        settings = self._settings.beta_zoom
        if not self._zoom_showing or not settings.zoom_enabled:
            return
        percent = stepped_zoom_percent(settings.zoom_percent, delta, maximum=self._zoom_effective_max_percent)
        if percent != settings.zoom_percent:
            self.set_beta_zoom_settings(replace(settings, zoom_percent=percent))

    def _sync_zoom_timer(self) -> None:
        settings = self._settings.beta_zoom
        should_run = settings.sidebar_enabled and (settings.live_enabled or settings.zoom_enabled)
        effective_mode = self._gpu_runtime_adaptation.effective_mode(settings.runtime_mode)
        interval = {"quiet": 120, "eco": 66, "fast": 33, "balanced": 33, "quality": 33}.get(effective_mode, 33)
        self._zoom_timer.setInterval(interval)
        if settings.auto_adapt_enabled and should_run:
            if not self._gpu_probe_timer.isActive():
                self._gpu_probe_timer.start()
        else:
            self._gpu_probe_timer.stop()
            if not should_run:
                if self._gpu_probe.state() != QProcess.ProcessState.NotRunning:
                    self._gpu_probe.terminate()
                self._gpu_runtime_adaptation.reset("GPU adaptation is idle until Zoom is active.")
            elif not settings.auto_adapt_enabled:
                self._gpu_runtime_adaptation.reset()
        if should_run and not self._wheel_hook.installed:
            self._wheel_hook.install()
        elif not should_run:
            self._wheel_hook.uninstall()
        if should_run and not self._zoom_timer.isActive():
            self._zoom_timer.start()
        elif not should_run and self._zoom_timer.isActive():
            self._zoom_timer.stop()
            self._hide_zoom_overlay()

    def _probe_gpu_runtime(self) -> None:
        if self._gpu_probe.state() != QProcess.ProcessState.NotRunning:
            return
        executable = shutil.which("nvidia-smi")
        if not executable:
            self._gpu_runtime_adaptation.unavailable()
            return
        self._gpu_probe.start(executable, ["--query-gpu=temperature.gpu,utilization.gpu",
                                           "--format=csv,noheader,nounits"])

    def _on_gpu_runtime_sample(self, exit_code: int, _exit_status) -> None:
        if exit_code != 0:
            self._gpu_runtime_adaptation.unavailable()
            return
        try:
            sample = bytes(self._gpu_probe.readAllStandardOutput()).decode("ascii", errors="strict").strip()
            temperature, utilization = (int(value.strip()) for value in sample.split(",", 1))
            previous_mode = self._gpu_runtime_adaptation.effective_mode(self._settings.beta_zoom.runtime_mode)
            self._gpu_runtime_adaptation.sample(self._settings.beta_zoom.runtime_mode, temperature, utilization)
            current_mode = self._gpu_runtime_adaptation.effective_mode(self._settings.beta_zoom.runtime_mode)
            if previous_mode != current_mode:
                self._sync_zoom_timer()
        except (UnicodeDecodeError, ValueError):
            self._gpu_runtime_adaptation.unavailable()

    def _on_gpu_probe_error(self, _error) -> None:
        self._gpu_runtime_adaptation.unavailable()

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
        available_source_side = min(frame_rect.width(), frame_rect.height())
        self._zoom_effective_max_percent = effective_zoom_max_percent(side, available_source_side)
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
        if self._zoom_showing or self._zoom_capture_active:
            self._zoom_overlay.hide_zoom()
            self._zoom_generation += 1
            self._zoom_processor.set_generation(self._zoom_generation)
        self._zoom_showing = False
        self._zoom_capture_active = False
        self._zoom_target_rect_current = None

    def _resolve_active_game_profile(self, running_names: set[str]) -> GameProfile | None:
        self._ambiguous_profile_matches = []
        if not running_names:
            return None
        profiles = [profile for profile in self._settings.game_profiles if profile.enabled and profile.style_id]
        matches = []
        for profile in profiles:
            names = {name.lower() for name in profile.executable_names if name}
            if profile.executable_path:
                names.add(Path(profile.executable_path).name.lower())
            if names & running_names:
                matches.append(profile)
        matches.sort(key=lambda item: (item.title.casefold(), item.game_id.casefold()))
        if len(matches) > 1:
            self._ambiguous_profile_matches = [item.title for item in matches]
        return matches[0] if matches else None

    def _debounce_fullscreen_state(self, detected: bool) -> bool:
        if detected:
            self._fullscreen_true_samples += 1
            self._fullscreen_false_samples = 0
            if self._fullscreen_true_samples >= 2:
                self._last_fullscreen_state = True
        else:
            self._fullscreen_false_samples += 1
            self._fullscreen_true_samples = 0
            if self._fullscreen_false_samples >= 3:
                self._last_fullscreen_state = False
        return self._last_fullscreen_state

    def _stable_active_game_profile(self, detected: GameProfile | None) -> GameProfile | None:
        if detected is not None:
            self._active_game_profile_misses = 0
            return detected
        if not self._settings.auto_switch_game_profiles or not self._active_game_profile_id:
            self._active_game_profile_misses = 0
            return None
        self._active_game_profile_misses += 1
        if self._active_game_profile_misses < 3:
            retained = self._profile_for_game(self._active_game_profile_id)
            if retained is not None and retained.enabled and retained.style_id in self._definitions:
                return retained
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

    @staticmethod
    def _selected_game_loadout(profile: GameProfile) -> GameLoadout | None:
        return next((item for item in profile.loadouts if item.loadout_id == profile.active_loadout_id), None)

    def _current_runtime_status(self) -> str:
        fullscreen_text = "fullscreen detected" if self._last_fullscreen_state else "windowed mode"
        ambiguity = " Ambiguous game match; using " + ", ".join(self._ambiguous_profile_matches) + "." if self._ambiguous_profile_matches else ""
        if self._active_game_profile_id:
            active_profile = self._profile_for_game(self._active_game_profile_id)
            if active_profile:
                return f"Runtime: {fullscreen_text}. Active game: {active_profile.title}.{ambiguity}"
        return f"Runtime: {fullscreen_text}. No mapped game currently running.{ambiguity}"

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
        self._input_timer.stop()
        self._wheel_hook.uninstall()
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self._hide_zoom_overlay()
        self._zoom_overlay.close()
        self._zoom_processor.stop()
        self._overlay.close()
        self._main_window.allow_close_once()
        self._main_window.close()
        self._app.quit()

    def _validated_style_id(self, style_id: str) -> str:
        return self._library.ensure_style_id(style_id)

    def _effective_style(self) -> OverlayStyle:
        profile = self._profile_for_game(getattr(self, "_active_game_profile_id", None) or "")
        loadout = self._selected_game_loadout(profile) if profile else None
        style_id = self._current_style_id
        ads_active = bool(getattr(self, "_ads_active", False))
        if ads_active and loadout and loadout.ads_style_id in self._definitions:
            style_id = loadout.ads_style_id
        base = self._definitions[style_id].style
        if loadout is not None:
            if ads_active:
                color = _parse_optional_rgba(loadout.ads_color_hex, base.color_rgba, loadout.ads_opacity_percent)
                outline = _parse_optional_rgba(loadout.ads_outline_color_hex, base.outline_rgba, loadout.ads_outline_opacity_percent)
            else:
                color = _parse_optional_rgba(loadout.color_hex, base.color_rgba, loadout.opacity_percent)
                outline = _parse_optional_rgba(loadout.outline_color_hex, base.outline_rgba, loadout.outline_opacity_percent)
            base = replace(base, color_rgba=color, outline_rgba=outline)
        combined = int(round((self._settings.selected_size_percent * self._settings.global_size_percent) / 100))
        return base.scaled(max(50, min(220, combined)))

    def _apply_theme(self) -> None:
        self._theme_manager.apply(theme_mode=self._settings.theme_mode, accent_hex=self._settings.accent_color)
        self._main_window.set_theme_values(self._settings.theme_mode, self._settings.accent_color, self._theme_manager.resolved_mode.value)
        self._main_window.set_beta_page_visible(self._settings.beta_zoom.sidebar_enabled)

    def _save_settings(self) -> None:
        self._config.save(self._settings)

    def set_library_metadata(self, collections: list[dict], tags: dict[str, list[str]]) -> None:
        self._settings.library_collections = [
            LibraryCollection(item["id"], item["name"], list(item["styleIds"])) for item in collections
        ]
        self._settings.library_tags = {key: list(value) for key, value in tags.items()}
        self._main_window.set_library_metadata(collections, tags)
        self._save_settings()

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
            zoom_percent=max(200, min(1600, int(settings.zoom_percent))),
            runtime_mode=settings.runtime_mode if settings.runtime_mode in {"quiet", "eco", "fast", "balanced", "quality"} else "balanced",
            auto_adapt_enabled=bool(settings.auto_adapt_enabled),
            zoom_in_hotkey_sequence=settings.zoom_in_hotkey_sequence.strip()[:128],
            zoom_out_hotkey_sequence=settings.zoom_out_hotkey_sequence.strip()[:128],
            zoom_reset_hotkey_sequence=settings.zoom_reset_hotkey_sequence.strip()[:128],
            animation_enabled=bool(settings.animation_enabled),
            animation_duration_ms=max(0, min(5000, int(settings.animation_duration_ms))),
            consume_mouse_wheel=bool(settings.consume_mouse_wheel),
            cleanup_enabled=bool(settings.cleanup_enabled),
            cleanup_radius=max(1, min(24, int(settings.cleanup_radius))),
            cleanup_strength=max(0, min(100, int(settings.cleanup_strength))),
            cleanup_preview=bool(settings.cleanup_preview),
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
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    start_to_tray = "--tray-start" in {arg.strip().lower() for arg in sys.argv[1:]}
    controller = AppController(app=app, start_to_tray=start_to_tray)
    controller.start()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()
