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
from crosshair_overlay.app import AppController, _WorkerReaper, _next_ads_state, _parse_optional_rgba
from crosshair_overlay.app_settings import AppSettings, GameLoadout, GameProfile, ReactiveSettings
from crosshair_overlay.creator.models import CreatorCrosshair, CreatorLayer
from crosshair_overlay.creator.conversion import creator_to_overlay_style
from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.crosshairs.io import load_xhair
from crosshair_overlay.crosshairs import CrosshairLibrary
from crosshair_overlay.storage_paths import StoragePaths
from crosshair_overlay.theme_manager import ThemeManager
from crosshair_overlay.ui.bridge_router import BridgeCommandRouter
from crosshair_overlay.hotkey_utils import parse_hotkey


class UiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.definitions = build_builtin_catalog()

    def test_bright_accent_gets_dark_button_text(self) -> None:
        manager = ThemeManager(self.app)
        self.assertEqual(manager._contrast_text("#FFFF00"), "#111615")
        self.assertEqual(manager._contrast_text("#223344"), "#FFFFFF")

    def test_game_loadout_appearance_survives_settings_round_trip(self) -> None:
        settings = AppSettings(game_profiles=[GameProfile(
            game_id="test", title="Test", source="manual", style_id="classic_cross",
            enabled=True, loadouts=[GameLoadout("one", "One", "classic_cross", color_hex="#12ABEF", opacity_percent=67,
                                                outline_color_hex="#010203", outline_opacity_percent=42)],
            active_loadout_id="one")])
        restored = AppSettings.from_dict(settings.to_dict())
        loadout = restored.game_profiles[0].loadouts[0]
        self.assertEqual((loadout.color_hex, loadout.opacity_percent), ("#12ABEF", 67))
        self.assertEqual((loadout.outline_color_hex, loadout.outline_opacity_percent), ("#010203", 42))

    def test_ads_toggle_changes_only_on_press_edges_and_hold_tracks_button(self) -> None:
        toggled, active = _next_ads_state("toggle", True, False, False)
        self.assertTrue(toggled and active)
        self.assertEqual(_next_ads_state("toggle", True, True, toggled), (True, True))
        self.assertEqual(_next_ads_state("toggle", False, True, toggled), (True, True))
        self.assertEqual(_next_ads_state("toggle", True, False, toggled), (False, False))
        self.assertEqual(_next_ads_state("hold", True, False, True), (False, True))
        self.assertEqual(_next_ads_state("hold", False, True, True), (False, False))

    def test_ads_settings_and_appearance_round_trip(self) -> None:
        settings = AppSettings(reactive=ReactiveSettings(ads_mode="toggle"))
        migrated = AppSettings.from_dict(settings.to_dict())
        self.assertEqual(migrated.reactive.ads_mode, "toggle")
        profile = GameProfile("game", "Game", "manual", style_id="classic_cross", enabled=True,
                              loadouts=[GameLoadout("main", "Main", "classic_cross", ads_style_id="dot_micro",
                                                    ads_color_hex="#AABBCC", ads_opacity_percent=55)],
                              active_loadout_id="main")
        loaded = AppSettings.from_dict(AppSettings(game_profiles=[profile]).to_dict()).game_profiles[0].loadouts[0]
        self.assertEqual((loaded.ads_style_id, loaded.ads_color_hex, loaded.ads_opacity_percent), ("dot_micro", "#AABBCC", 55))

    def test_optional_loadout_color_preserves_base_alpha_and_opacity(self) -> None:
        self.assertEqual(_parse_optional_rgba("#123456", (200, 100, 50, 180), 50), (18, 52, 86, 90))
        self.assertEqual(_parse_optional_rgba("", (200, 100, 50, 180), 0), (200, 100, 50, 0))

    def test_effective_style_switches_ads_style_and_appearance_without_losing_hip_style(self) -> None:
        class ControllerHarness:
            _effective_style = AppController._effective_style
            _selected_game_loadout = staticmethod(AppController._selected_game_loadout)

            def __init__(self, ads_active):
                self._definitions = UiRegressionTests.definitions
                self._active_game_profile_id = "game"
                self._current_style_id = "classic_cross"
                self._ads_active = ads_active
                self._settings = SimpleNamespace(selected_size_percent=100, global_size_percent=100)
                self.profile = GameProfile(
                    "game", "Game", "manual", style_id="classic_cross", enabled=True,
                    loadouts=[GameLoadout("main", "Main", "classic_cross", color_hex="#112233",
                                          ads_style_id="dot_micro", ads_color_hex="#AABBCC")],
                    active_loadout_id="main")

            def _profile_for_game(self, game_id):
                return self.profile if game_id == "game" else None

        hip = ControllerHarness(False)._effective_style()
        ads = ControllerHarness(True)._effective_style()
        self.assertEqual(hip.style_id, "classic_cross")
        self.assertEqual(hip.color_rgba[:3], (17, 34, 51))
        self.assertEqual(ads.style_id, "dot_micro")
        self.assertEqual(ads.color_rgba[:3], (170, 187, 204))

    def test_game_loadout_bridge_validates_appearance_fields(self) -> None:
        definition = self.definitions["classic_cross"]
        valid = {"loadout_id": "main", "name": "Main", "style_id": "classic_cross", "zoom_percent": 200,
                 "fire_pulse": True, "gap_expansion": True, "opacity_pulse": False, "hide_on_ads": False,
                 "fire_duration_ms": 120, "fire_amplitude_percent": 18, "ads_transition_ms": 80,
                 "color_hex": "#aabbcc", "opacity_percent": 75, "outline_color_hex": "", "outline_opacity_percent": 100,
                 "ads_style_id": "dot_micro", "ads_color_hex": "#112233", "ads_opacity_percent": 80,
                 "ads_outline_color_hex": "", "ads_outline_opacity_percent": 100}
        normalized = BridgeCommandRouter._game_loadouts([valid], {"classic_cross": definition, "dot_micro": self.definitions["dot_micro"]})
        self.assertEqual(normalized[0]["color_hex"], "#AABBCC")
        invalid = {**valid, "color_hex": "red"}
        with self.assertRaises(ValueError):
            BridgeCommandRouter._game_loadouts([invalid], {"classic_cross": definition, "dot_micro": self.definitions["dot_micro"]})

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

    def test_monitor_offset_bridge_accepts_known_monitor_and_rejects_bad_coordinates(self) -> None:
        class Signal:
            def __init__(self): self.value = None
            def emit(self, *value): self.value = value

        class Window:
            _beta_monitors = [("screen:0", "Primary")]
            monitor_offset_changed = Signal()

        window = Window()
        router = BridgeCommandRouter(window)
        router.dispatch("setMonitorOffset", {"monitorId": "screen:0", "x": -9, "y": 13})
        self.assertEqual(window.monitor_offset_changed.value, ("screen:0", -9, 13))
        with self.assertRaises(ValueError):
            router.dispatch("setMonitorOffset", {"monitorId": "screen:0", "x": 129, "y": 0})

    def test_typing_state_bridge_accepts_only_boolean_and_updates_native_guard(self) -> None:
        class Window:
            keyboard_entry_active = False

        window = Window()
        router = BridgeCommandRouter(window)
        router.dispatch("setTypingState", {"active": True})
        self.assertTrue(window.keyboard_entry_active)
        with self.assertRaises(ValueError):
            router.dispatch("setTypingState", {"active": "true"})

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

    def test_zoom_hotkey_is_ignored_while_react_text_entry_has_focus(self) -> None:
        class WindowHarness:
            keyboard_entry_active = True

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
                raise AssertionError("text entry must suppress the zoom hotkey before capture")

        controller = ControllerHarness()
        with patch("crosshair_overlay.app.is_hotkey_pressed", return_value=True):
            controller._zoom_tick()
        self.assertTrue(controller.hidden)

    def test_n_is_a_supported_global_zoom_key(self) -> None:
        spec = parse_hotkey(AppSettings().beta_zoom.hotkey_sequence)
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key_code, ord("N"))

    def test_zoom_hides_and_restores_crosshair_when_preference_is_enabled(self) -> None:
        class Overlay:
            visible = True

            def isVisible(self):
                return self.visible

            def hide(self):
                self.visible = False

            def show(self):
                self.visible = True

        class ControllerHarness:
            _update_zoom_crosshair_visibility = AppController._update_zoom_crosshair_visibility

            def __init__(self):
                self._settings = AppSettings()
                self._settings.beta_zoom.hide_crosshair_when_zoomed = True
                self._overlay = Overlay()
                self._zoom_crosshair_was_visible = False
                self._overlay_visible = True
                self._emergency_hidden = False
                self._ads_suppressed = False

        controller = ControllerHarness()
        controller._update_zoom_crosshair_visibility(True)
        self.assertFalse(controller._overlay.visible)
        self.assertTrue(controller._zoom_crosshair_was_visible)
        controller._update_zoom_crosshair_visibility(False)
        self.assertTrue(controller._overlay.visible)
        self.assertFalse(controller._zoom_crosshair_was_visible)

    def test_creator_save_bridge_propagates_filesystem_failure(self) -> None:
        class Signal:
            def emit(self, *_args):
                raise AssertionError("fire-and-forget creator save must not be used")

        class Window:
            creator_save_requested = Signal()

            @staticmethod
            def creator_save_handler(_model, _activate):
                raise OSError("storage is read-only")

        router = BridgeCommandRouter(Window())
        model = {
            "format": "crosshair-overlay-creator-v3",
            "version": 3,
            "name": "Saved Test",
            "grid_size": 32,
            "creation_mode": "draw",
            "color_hex": "#FFFFFF",
            "filled_cells": [[15, 15]],
            "style_id": "",
            "created_at": "",
            "updated_at": "",
            "layers": [],
        }
        with self.assertRaisesRegex(OSError, "read-only"):
            router.dispatch("creatorSave", {"model": model, "activate": False})

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
            first_result = controller.save_creator_crosshair(source, activate_now=False)
            self.assertFalse(warning.called, warning.call_args)
            saved = controller._main_window.creator_model
            self.assertEqual(saved.style_id, "classic_cross_2")
            self.assertEqual(first_result, {"accepted": True, "styleId": saved.style_id, "name": "Classic Cross"})
            destination = controller._storage_paths.creator_definition_path(saved.style_id)
            self.assertTrue(destination.exists())

            saved.name = "Renamed Creator Cross"
            updated_result = controller.save_creator_crosshair(saved, activate_now=False)
            self.assertTrue(updated_result["accepted"])
            self.assertEqual(updated_result["styleId"], saved.style_id)
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


    def test_creator_v2_remains_flat_and_round_trips(self) -> None:
        model = CreatorCrosshair("Legacy", 32, "#FFFFFF", [(2, 3), (2, 3)])
        payload = model.to_dict()
        self.assertEqual(payload["format"], "crosshair-overlay-creator-v2")
        self.assertNotIn("layers", payload)
        restored = CreatorCrosshair.from_dict(payload)
        self.assertEqual(restored.normalized_cells(), [(2, 3)])

    def test_creator_v3_keeps_hidden_layers_but_flattens_visible_cells(self) -> None:
        model = CreatorCrosshair("Layered", 32, "#FFFFFF", [], layers=[
            CreatorLayer("visible", "Visible", "cross", True, [(3, 4)]),
            CreatorLayer("hidden", "Hidden", "dot", False, [(7, 8)]),
        ])
        payload = model.to_dict()
        restored = CreatorCrosshair.from_dict(payload)
        self.assertEqual(payload["format"], "crosshair-overlay-creator-v3")
        self.assertEqual([layer.layer_id for layer in restored.layers], ["visible", "hidden"])
        self.assertEqual(restored.normalized_cells(), [(3, 4)])
        self.assertEqual(creator_to_overlay_style(restored).custom_filled_cells, ((3, 4),))

    def test_creator_bridge_rejects_out_of_grid_layer_cells(self) -> None:
        payload = CreatorCrosshair("Layered", 32, "#FFFFFF", [], layers=[
            CreatorLayer("visible", "Visible", "draw", True, [(3, 4)])
        ]).to_dict()
        payload["layers"][0]["filled_cells"] = [[32, 0]]
        with self.assertRaises(ValueError):
            BridgeCommandRouter._creator_model(payload)

    def test_library_metadata_validates_collections_and_normalizes_bulk_tags(self) -> None:
        definitions = {"dot_micro": self.definitions["dot_micro"]}
        collections, tags = BridgeCommandRouter._library_metadata(
            [{"id": "collection-1", "name": "Aim", "styleIds": ["dot_micro"]}],
            {"dot_micro": ["  sniper ", "sniper", "micro"]}, definitions)
        self.assertEqual(collections[0]["styleIds"], ["dot_micro"])
        self.assertEqual(tags, {"dot_micro": ["sniper", "micro"]})
        with self.assertRaises(ValueError):
            BridgeCommandRouter._library_metadata(
                [{"id": "collection-1", "name": "Aim", "styleIds": ["missing"]}], {}, definitions)

    def test_duplicate_detection_ignores_color_but_matches_geometry(self) -> None:
        first = self.definitions["classic_cross"]
        altered_style = replace(first.style, style_id="classic_cross_alt", display_name="Same geometry, new color",
                                color_rgba=(0, 255, 0, 255))
        second = replace(first, style=altered_style)
        router = BridgeCommandRouter(SimpleNamespace(_definitions={first.style_id: first, second.style_id: second}))
        groups = router._find_duplicates()
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]["styleIds"]), {first.style_id, second.style_id})

    def test_collection_filter_and_bulk_tags_participate_in_catalog_search(self) -> None:
        class WindowHarness:
            _definitions = {"dot_micro": UiRegressionTests.definitions["dot_micro"],
                            "classic_cross": UiRegressionTests.definitions["classic_cross"]}
            _library_collections = [{"id": "focused", "name": "Focused", "styleIds": ["dot_micro"]}]
            _library_tags = {"dot_micro": ["sniper"]}
            _recent_style_ids: list[str] = []

            @staticmethod
            def _style_payload(item):
                return {"id": item.style_id}

        router = BridgeCommandRouter(WindowHarness())
        collected = router.dispatch("queryCatalog", {"query": "", "filter": "collection:focused", "page": 0, "pageSize": 36})
        tagged = router.dispatch("queryCatalog", {"query": "sniper", "filter": "all", "page": 0, "pageSize": 36})
        self.assertEqual((collected["total"], collected["styles"][0]["id"]), (1, "dot_micro"))
        self.assertEqual((tagged["total"], tagged["styles"][0]["id"]), (1, "dot_micro"))

    def test_imported_xhair_preserves_catalog_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = AppController.__new__(AppController)
            controller._definitions = {}
            original = replace(self.definitions["dot_micro"], aliases=("micro dot",), origin_game="Example FPS",
                               author="Community", source_url="https://example.invalid/style",
                               reuse_status="attribution", approximate=True, catalog_version=3)
            stored = controller._store_imported_definition(original, Path(temp_dir) / "items", "imported_pack")
            restored = load_xhair(Path(temp_dir) / "items" / f"{stored.style_id}.xhair")
            self.assertEqual(restored.aliases, ("micro dot",))
            self.assertEqual(restored.origin_game, "Example FPS")
            self.assertEqual(restored.author, "Community")
            self.assertEqual(restored.source_url, "https://example.invalid/style")
            self.assertEqual(restored.reuse_status, "attribution")
            self.assertTrue(restored.approximate)
            self.assertEqual(restored.catalog_version, 3)

    def test_import_conflict_preview_detects_id_and_case_insensitive_name(self) -> None:
        by_id = self.definitions["dot_micro"]
        by_name = replace(self.definitions["classic_cross"],
                          style=replace(self.definitions["classic_cross"].style,
                                        style_id="new-id", display_name=by_id.display_name.upper()))
        clean = replace(self.definitions["classic_cross"],
                        style=replace(self.definitions["classic_cross"].style,
                                      style_id="another-id", display_name="Fresh style"))
        conflicts = AppController._find_import_conflicts([by_id, by_name, clean], {by_id.style_id: by_id})
        self.assertEqual(conflicts, [by_id, by_name])

    def test_catalog_searchable_text_is_cached_per_immutable_definition(self) -> None:
        original = self.definitions["dot_micro"]
        self.assertIn(original.display_name.casefold(), original.searchable_text)
        updated = replace(original, style=replace(original.style, display_name="Updated violet reticle"))
        self.assertIn("updated violet reticle", updated.searchable_text)
        self.assertNotIn("updated violet reticle", original.searchable_text)

    def test_import_replace_is_limited_to_user_custom_xhair_and_writes_atomically(self) -> None:
        with tempfile.TemporaryDirectory(dir="artifacts") as temp_dir:
            paths = StoragePaths(Path(temp_dir) / "library")
            paths.ensure()
            destination = paths.custom_definition_path("safe-style")
            original = replace(self.definitions["dot_micro"],
                               style=replace(self.definitions["dot_micro"].style,
                                             style_id="safe-style", display_name="Safe Style"),
                               source_type="custom", source_path=str(destination))
            from crosshair_overlay.crosshairs.io import save_xhair
            save_xhair(original, destination)

            controller = AppController.__new__(AppController)
            controller._storage_paths = paths
            self.assertTrue(controller._is_replaceable_import_conflict(original))
            self.assertFalse(controller._is_replaceable_import_conflict(self.definitions["dot_micro"]))

            incoming = replace(original, style=replace(original.style, arm_length=17))
            AppController._write_xhair_atomically(incoming, destination)
            self.assertEqual(load_xhair(destination).style.arm_length, 17)
            self.assertFalse(destination.with_name(destination.name + ".import.tmp").exists())

if __name__ == "__main__":
    unittest.main()
