from __future__ import annotations

import os
import tempfile
import unittest
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from PySide6.QtWidgets import QApplication

from crosshair_overlay.config import OverlayStyle
from crosshair_overlay.app import AppController, _WorkerReaper
from crosshair_overlay.app_settings import AppSettings, GameProfile
from crosshair_overlay.creator.models import CreatorCrosshair
from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.crosshairs import CrosshairLibrary
from crosshair_overlay.storage_paths import StoragePaths
from crosshair_overlay.theme_manager import ThemeManager
from crosshair_overlay.ui.bridge_router import BridgeCommandRouter


class UiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.definitions = build_builtin_catalog()

    def test_bright_accent_gets_dark_button_text(self) -> None:
        manager = ThemeManager(self.app)
        self.assertEqual(manager._contrast_text("#FFFF00"), "#111615")
        self.assertEqual(manager._contrast_text("#223344"), "#FFFFFF")

    def test_catalog_query_is_bounded_for_ten_thousand_styles(self) -> None:
        class Window:
            def __init__(self) -> None:
                self._definitions = OrderedDict()

            @staticmethod
            def _style_payload(item):
                return {"id": item.style_id, "name": item.display_name}

        window = Window()
        for index in range(10_000):
            item = SimpleNamespace(
                style_id=f"style-{index}", display_name=f"Benchmark {index:05d}",
                family="Benchmark", source_type="custom" if index % 5 == 0 else "builtin",
                tags=("performance",), is_favorite=index % 7 == 0,
            )
            window._definitions[item.style_id] = item
        router = BridgeCommandRouter(window)
        result = router.dispatch("queryCatalog", {"query": "benchmark", "filter": "all", "page": 0, "pageSize": 36})
        self.assertEqual(result["total"], 10_000)
        self.assertEqual(len(result["styles"]), 36)
        match = router.dispatch("queryCatalog", {"query": "benchmark 09999", "filter": "all", "page": 0, "pageSize": 36})
        self.assertEqual(match["total"], 1)
        self.assertEqual(match["styles"][0]["id"], "style-9999")

    def test_catalog_query_rejects_oversized_pages(self) -> None:
        class Window:
            _definitions = OrderedDict()
        router = BridgeCommandRouter(Window())
        with self.assertRaises(ValueError):
            router.dispatch("queryCatalog", {"query": "", "filter": "all", "page": 0, "pageSize": 100_000})

    def test_navigation_has_no_classic_surface_fallback(self) -> None:
        class Window:
            _web_page = "home"
            _current_page_id = "home"

        window = Window()
        router = BridgeCommandRouter(window)
        router.dispatch("navigate", {"page": "zoom"})
        self.assertEqual(window._current_page_id, "zoom")
        with self.assertRaises(ValueError):
            router.dispatch("toggleNative", {})

    def test_fullscreen_detection_ignores_one_tick_flaps(self) -> None:
        controller = AppController.__new__(AppController)
        controller._last_fullscreen_state = False
        controller._fullscreen_true_samples = 0
        controller._fullscreen_false_samples = 0
        self.assertFalse(controller._debounce_fullscreen_state(True))
        self.assertTrue(controller._debounce_fullscreen_state(True))
        self.assertTrue(controller._debounce_fullscreen_state(False))
        self.assertTrue(controller._debounce_fullscreen_state(True))
        self.assertTrue(controller._debounce_fullscreen_state(False))
        self.assertTrue(controller._debounce_fullscreen_state(False))
        self.assertFalse(controller._debounce_fullscreen_state(False))

    def test_game_overlay_profile_survives_transient_process_scan_misses(self) -> None:
        class ControllerHarness:
            _stable_active_game_profile = AppController._stable_active_game_profile

            def __init__(self):
                self._settings = AppSettings(auto_switch_game_profiles=True)
                self._active_game_profile_id = "game-a"
                self._active_game_profile_misses = 0
                self._definitions = {"dot_micro": object()}
                self.profile = GameProfile("game-a", "Game A", "manual", style_id="dot_micro", enabled=True)

            def _profile_for_game(self, game_id):
                return self.profile if game_id == self.profile.game_id else None

        controller = ControllerHarness()
        self.assertIs(controller._stable_active_game_profile(None), controller.profile)
        self.assertIs(controller._stable_active_game_profile(None), controller.profile)
        self.assertIsNone(controller._stable_active_game_profile(None))
        self.assertIs(controller._stable_active_game_profile(controller.profile), controller.profile)
        self.assertEqual(controller._active_game_profile_misses, 0)

    def test_zoom_page_without_live_zoom_does_not_capture_frames(self) -> None:
        class WindowHarness:
            current_page_id = "zoom"

            def isVisible(self):
                return True

        class ControllerHarness:
            _zoom_tick = AppController._zoom_tick

            def __init__(self):
                self._settings = AppSettings()
                self._settings.beta_zoom.sidebar_enabled = True
                self._settings.beta_zoom.zoom_enabled = True
                self._settings.beta_zoom.live_enabled = False
                self._main_window = WindowHarness()
                self._zoom_hotkey = object()
                self.hidden = False

            def _hide_zoom_overlay(self):
                self.hidden = True

            def _current_zoom_source_frame(self):
                raise AssertionError("inactive zoom must not capture the screen")

        controller = ControllerHarness()
        with patch("crosshair_overlay.app.is_hotkey_pressed", return_value=False):
            controller._zoom_tick()
        self.assertTrue(controller.hidden)

    def test_new_creator_save_avoids_builtin_ids_and_existing_creator_is_updated(self) -> None:
        class ControllerHarness:
            _creator_style_id = AppController._creator_style_id
            _next_available_style_id = AppController._next_available_style_id
            _slugify = AppController._slugify

            def __init__(self, storage: Path) -> None:
                self._definitions = build_builtin_catalog()
                self._storage_paths = StoragePaths(storage)

        controller = ControllerHarness(Path(tempfile.gettempdir()) / "crosshair-creator-id-test")
        model = CreatorCrosshair("Classic Cross", 32, "#FFFFFF", [])
        self.assertEqual(controller._creator_style_id(model, model.name), "classic_cross_2")
        controller._definitions["creator_test"] = replace(
            self.definitions["classic_cross"], style=OverlayStyle(**{**self.definitions["classic_cross"].style.__dict__, "style_id": "creator_test"}), source_type="creator_grid"
        )
        model.style_id = "creator_test"
        self.assertEqual(controller._creator_style_id(model, model.name), "creator_test")

    def test_creator_save_returns_assigned_id_and_repeat_save_updates_same_file(self) -> None:
        class WindowHarness:
            creator_model = None

            def refresh_definitions(self, definitions, selected_style_id):
                self.definitions = definitions
                self.selected_style_id = selected_style_id

            def set_creator_model(self, model):
                self.creator_model = model

        class ControllerHarness:
            save_creator_crosshair = AppController.save_creator_crosshair
            _creator_style_id = AppController._creator_style_id
            _next_available_style_id = AppController._next_available_style_id
            _slugify = AppController._slugify
            _hydrate_favorites = AppController._hydrate_favorites

            def __init__(self, storage: Path) -> None:
                self._definitions = build_builtin_catalog()
                self._library = CrosshairLibrary()
                self._storage_paths = StoragePaths(storage)
                self._storage_paths.ensure()
                self._settings = AppSettings(crosshair_storage_path=str(storage))
                self._main_window = WindowHarness()

            def _refresh_games_page(self):
                pass

        with tempfile.TemporaryDirectory() as tmp, \
                patch("crosshair_overlay.app.QMessageBox.information"), \
                patch("crosshair_overlay.app.QMessageBox.warning") as warning:
            controller = ControllerHarness(Path(tmp))
            source = CreatorCrosshair("Classic Cross", 32, "#67D4AE", [(15, 15)])
            controller.save_creator_crosshair(source, activate_now=False)
            self.assertFalse(warning.called, warning.call_args)
            saved = controller._main_window.creator_model
            self.assertEqual(saved.style_id, "classic_cross_2")
            destination = controller._storage_paths.creator_definition_path(saved.style_id)
            self.assertTrue(destination.exists())

            saved.name = "Renamed Creator Cross"
            controller.save_creator_crosshair(saved, activate_now=False)
            self.assertEqual(controller._main_window.creator_model.style_id, saved.style_id)
            self.assertEqual(len([d for d in controller._definitions.values() if d.source_type == "creator_grid"]), 1)

    def test_worker_reaper_preserves_64_bit_keys(self) -> None:
        reaper = _WorkerReaper()
        received: list[int] = []
        reaper.released.connect(received.append)
        key = (1 << 40) + 57
        reaper.released.emit(key)
        self.assertEqual(received, [key])

    def test_startup_update_check_respects_user_preference(self) -> None:
        class ControllerHarness:
            _check_updates_on_startup = AppController._check_updates_on_startup
            _handle_startup_update_result = AppController._handle_startup_update_result

            def __init__(self, enabled: bool) -> None:
                self._settings = AppSettings(auto_update_on_startup=enabled)
                self._update_check_running = False
                self._update_manager = object()
                self.workers = []

            def _start_worker(self, worker):
                self.workers.append(worker)

        disabled = ControllerHarness(False)
        disabled._check_updates_on_startup()
        self.assertEqual(disabled.workers, [])
        enabled = ControllerHarness(True)
        enabled._check_updates_on_startup()
        self.assertEqual(len(enabled.workers), 1)


if __name__ == "__main__":
    unittest.main()

