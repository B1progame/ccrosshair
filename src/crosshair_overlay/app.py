from __future__ import annotations

import re
import json
import signal
import sys
import shutil
import ctypes
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .app_settings import AppSettings, GameProfile, ThemeMode
from .config import OverlayStyle
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
from .overlay_window import OverlayWindow
from .storage_paths import StoragePaths
from .style_registry import load_style_pack, save_style_pack
from .theme_manager import ThemeManager
from .game_services import DiscoveredGame, scan_game_libraries
from .windows_runtime import foreground_monitor_bounds, is_foreground_fullscreen, running_process_names
from .ui.main_window import MainWindow
from .ui.pages.games_page import GameRowModel


class AppController(QObject):
    """Coordinates app shell, overlay state, and persistence."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._config = ConfigManager()
        self._settings = self._config.load()
        self._storage_paths = StoragePaths(Path(self._settings.crosshair_storage_path))
        self._storage_paths.ensure()
        self._theme_manager = ThemeManager(app=self._app)

        self._library = CrosshairLibrary()
        self._definitions = self._library.load(self._storage_paths.root)
        self._hydrate_favorites()

        self._current_style_id = self._validated_style_id(self._settings.selected_style_id)
        self._overlay = OverlayWindow(style=self._effective_style())
        self._main_window = MainWindow(
            definitions=self._definitions,
            current_style_id=self._current_style_id,
            selected_size_percent=self._settings.selected_size_percent,
            theme_mode=self._settings.theme_mode,
            accent_color=self._settings.accent_color,
            global_size_percent=self._settings.global_size_percent,
            storage_path=self._settings.crosshair_storage_path,
            sidebar_collapsed=self._settings.sidebar_collapsed,
        )
        self._overlay_visible = bool(self._settings.overlay_enabled)
        self._manual_overlay_enabled = bool(self._settings.overlay_enabled)
        self._manual_style_id = self._current_style_id
        self._auto_applied_style_id: str | None = None
        self._active_game_profile_id: str | None = None
        self._last_fullscreen_state = False
        self._discovered_games: list[DiscoveredGame] = []
        self._automation_timer = QTimer(self)
        self._automation_timer.setInterval(1100)
        self._automation_timer.timeout.connect(self._automation_tick)
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._is_quitting = False
        self._wire_signals()
        self._apply_theme()
        self._reload_games()
        self._setup_tray()

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
        self._main_window.check_updates_requested.connect(self.show_updates_placeholder)
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
        self._main_window.close_to_tray_requested.connect(self.hide_main_window_to_tray)

    def start(self) -> None:
        if self._overlay_visible:
            self._overlay.show()
            self._main_window.set_overlay_status(True)
        else:
            self._overlay.hide()
            self._main_window.set_overlay_status(False)

        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()
        self._main_window.set_selected_style(self._current_style_id)
        self._main_window.set_selected_style_name(self._definitions[self._current_style_id].display_name)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._main_window.set_selected_size(self._settings.selected_size_percent)
        self._main_window.set_global_size(self._settings.global_size_percent)
        self._main_window.set_storage_path(self._settings.crosshair_storage_path)
        self._refresh_games_page()
        self._main_window.navigate_to("home")
        self._automation_timer.start()
        self._automation_tick()
        if self._tray_icon is not None:
            self._tray_icon.show()

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
        if definition.style_id != self._current_style_id:
            self.set_overlay_style(definition.style_id)
        else:
            self._overlay.set_style(self._effective_style())
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id)
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

    def import_pack(self, pack_path: str) -> None:
        try:
            source = Path(pack_path)
            suffix = source.suffix.lower()
            bundle_dir = self._storage_paths.create_import_bundle(source.stem)
            items_dir = bundle_dir / "items"
            saved_ids: list[str] = []

            if suffix == XHAIR_EXTENSION:
                definition = load_xhair(source)
                stored = self._store_imported_definition(definition, items_dir, source_type="imported_pack")
                saved_ids.append(stored.style_id)
                shutil.copy2(source, bundle_dir / source.name)
            elif suffix == XPACK_EXTENSION:
                definitions = load_xpack(source)
                for definition in definitions:
                    stored = self._store_imported_definition(definition, items_dir, source_type="imported_pack")
                    saved_ids.append(stored.style_id)
                shutil.copy2(source, bundle_dir / source.name)
            elif suffix == ".chgrid":
                creator_model = load_creator_crosshair(source)
                target_id = self._next_available_style_id(self._slugify(creator_model.style_id or creator_model.name), items_dir, ".chgrid")
                creator_model.style_id = target_id
                target = items_dir / f"{target_id}.chgrid"
                save_creator_crosshair(creator_model, target)
                saved_ids.append(target_id)
            else:
                style = load_style_pack(source)
                definition = CrosshairDefinition(
                    style=style,
                    family="Legacy Pack",
                    description="Imported from legacy .chpack.",
                    tags=("legacy", "pack"),
                    editable_settings=self._definitions[default_style_id()].editable_settings,
                    source_type="legacy_pack",
                )
                stored = self._store_imported_definition(definition, items_dir, source_type="legacy_pack")
                saved_ids.append(stored.style_id)
                shutil.copy2(source, bundle_dir / source.name)

            manifest = {
                "imported_at": datetime.now().isoformat(timespec="seconds"),
                "source_name": source.name,
                "source_suffix": suffix,
                "imported_style_ids": saved_ids,
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
        self._settings = AppSettings(
            crosshair_storage_path=self._settings.crosshair_storage_path or str(self._config.default_crosshair_path)
        )
        self._definitions = self._library.load(Path(self._settings.crosshair_storage_path))
        self._current_style_id = self._validated_style_id(self._settings.selected_style_id)
        self._manual_style_id = self._current_style_id
        self._auto_applied_style_id = None
        self._active_game_profile_id = None
        self._overlay.set_style(self._effective_style())
        self._main_window.refresh_definitions(self._definitions, selected_style_id=self._current_style_id)
        self._main_window.set_selected_style(self._current_style_id)
        self._main_window.set_selected_style_name(self._definitions[self._current_style_id].display_name)
        self._main_window.set_active_style_preview(self._definitions[self._current_style_id])
        self._main_window.set_selected_size(self._settings.selected_size_percent)
        self._main_window.set_global_size(self._settings.global_size_percent)
        self._main_window.set_theme_values(self._settings.theme_mode, self._settings.accent_color)
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
        self._save_settings()

    def show_updates_placeholder(self) -> None:
        QMessageBox.information(
            self._main_window,
            "Updates",
            "Automatic update downloads will be integrated in a later phase.",
        )

    def save_creator_crosshair(self, model: object, activate_now: bool) -> None:
        if not isinstance(model, CreatorCrosshair):
            return
        try:
            style = creator_to_overlay_style(model)
            style = style_with_updates(style, {"style_id": self._slugify(style.display_name)})
            creator_model = CreatorCrosshair(
                name=model.name,
                grid_size=model.grid_size,
                creation_mode=model.creation_mode,
                color_hex=model.color_hex,
                filled_cells=model.normalized_cells(),
                style_id=style.style_id,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            destination = self._storage_paths.creator_definition_path(style.style_id)
            save_creator_crosshair(creator_model, destination)

            self._definitions = self._library.load(self._storage_paths.root)
            self._hydrate_favorites()

            self._main_window.refresh_definitions(self._definitions, selected_style_id=style.style_id)
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
            is_favorite=definition.is_favorite,
        )
        destination = items_dir / f"{target_id}.xhair"
        save_xhair(stored, destination)
        return stored

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
            self._restore_manual_style_if_needed()
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
        self._discovered_games = scan_game_libraries()
        self._sync_profiles_with_discovery()

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

        active_profile = self._resolve_active_game_profile(running_names)

        should_show_overlay = self._manual_overlay_enabled
        if self._settings.auto_enable_on_fullscreen:
            should_show_overlay = fullscreen
        if self._settings.auto_switch_game_profiles and active_profile is not None:
            should_show_overlay = True

        self._set_overlay_visible(should_show_overlay, persist=False)

        if self._overlay_visible:
            if monitor_bounds is not None:
                self._overlay.center_on_bounds(*monitor_bounds)
            else:
                self._overlay.center_on_primary_screen()

        if self._settings.auto_switch_game_profiles and active_profile is not None:
            if active_profile.style_id in self._definitions:
                if self._active_game_profile_id != active_profile.game_id:
                    self._active_game_profile_id = active_profile.game_id
                    self._auto_applied_style_id = active_profile.style_id
                    self.set_overlay_style(active_profile.style_id, persist=False)
        else:
            self._restore_manual_style_if_needed()
            self._active_game_profile_id = None

        self._main_window.set_games_status(self._current_runtime_status())

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
        if self._tray_icon is not None:
            self._tray_icon.hide()
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
        self._main_window.set_theme_values(self._settings.theme_mode, self._settings.accent_color)

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


def run() -> int:
    """Application entry point."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CrosshairOverlay.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    logo_path = Path(__file__).resolve().parent / "assets" / "logo.svg"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    controller = AppController(app=app)
    controller.start()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()
