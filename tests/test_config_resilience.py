from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from crosshair_overlay.app_settings import AppSettings
from crosshair_overlay.config_manager import ConfigManager
from crosshair_overlay.storage_paths import StoragePaths


class ConfigResilienceTests(unittest.TestCase):
    def make_manager(self, root: Path) -> ConfigManager:
        manager = ConfigManager.__new__(ConfigManager)
        manager._app_dir = root
        manager._settings_file = root / "settings.json"
        manager._crosshair_dir = root / "crosshairs"
        manager._storage = StoragePaths(manager._crosshair_dir)
        manager._app_dir.mkdir(parents=True, exist_ok=True)
        manager._storage.ensure()
        manager.last_load_warning = ""
        return manager

    def test_legacy_settings_migrate_and_invalid_numbers_fall_back(self) -> None:
        settings = AppSettings.from_dict({"beta_zoom": {"zoom_percent": "bad", "position_x_percent": None}})
        self.assertEqual(settings.schema_version, 8)
        self.assertEqual(settings.beta_zoom.zoom_percent, 200)
        self.assertEqual(settings.beta_zoom.position_x_percent, 50)

    def test_monitor_offsets_migrate_with_bounds_and_drop_malformed_entries(self) -> None:
        settings = AppSettings.from_dict({"monitor_offsets": {
            "screen:0": {"x": -24, "y": 18},
            "screen:1": {"x": 129, "y": 0},
            "screen:2": {"x": True, "y": 0},
            "invalid": [1, 2],
        }})
        self.assertEqual(settings.monitor_offsets, {"screen:0": {"x": -24, "y": 18}})

    def test_library_collections_and_tags_migrate_with_bounds(self) -> None:
        settings = AppSettings.from_dict({
            "library_collections": [
                {"collection_id": "aim", "name": " Aim ", "style_ids": ["dot", "dot", "cross"]},
                {"collection_id": "aim", "name": "Duplicate", "style_ids": ["other"]},
                {"collection_id": "invalid", "name": "", "style_ids": []},
            ],
            "library_tags": {"dot": [" Sniper ", "sniper", "tiny"], "bad": ["ok"], "cross": "bad"},
        })
        self.assertEqual(settings.schema_version, 8)
        self.assertEqual([(item.collection_id, item.name, item.style_ids) for item in settings.library_collections],
                         [("aim", "Aim", ["dot", "cross"])])
        self.assertEqual(settings.library_tags, {"dot": ["sniper", "tiny"], "bad": ["ok"]})
        restored = AppSettings.from_dict(settings.to_dict())
        self.assertEqual(restored.library_collections[0].style_ids, ["dot", "cross"])
        self.assertEqual(restored.library_tags, settings.library_tags)

    def test_corrupt_file_is_preserved_and_valid_backup_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            manager = self.make_manager(Path(tmp))
            manager.backup_path.write_text(json.dumps({"selected_style_id": "dot_micro"}), encoding="utf-8")
            manager.settings_path.write_text("{broken", encoding="utf-8")

            loaded = manager.load()

            self.assertEqual(loaded.selected_style_id, "dot_micro")
            self.assertTrue(manager.last_load_warning)
            self.assertEqual(manager.backup_path.read_text(encoding="utf-8"), '{"selected_style_id": "dot_micro"}')
            preserved = Path(tmp) / "settings.corrupt.json"
            self.assertTrue(preserved.exists())
            self.assertEqual(preserved.read_text(encoding="utf-8"), "{broken")

    def test_save_keeps_previous_valid_settings_as_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            manager = self.make_manager(Path(tmp))
            manager.settings_path.write_text(json.dumps({"selected_style_id": "dot_micro"}), encoding="utf-8")

            manager.save(AppSettings(selected_style_id="classic_cross"))

            self.assertEqual(json.loads(manager.backup_path.read_text(encoding="utf-8"))["selected_style_id"], "dot_micro")
            self.assertEqual(json.loads(manager.settings_path.read_text(encoding="utf-8"))["selected_style_id"], "classic_cross")

    def test_backup_preview_is_grouped_and_restore_keeps_current_state_as_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            manager = self.make_manager(Path(tmp))
            original = AppSettings(selected_style_id="dot_micro", accent_color="#123456")
            manager.settings_path.write_text(json.dumps(original.to_dict()), encoding="utf-8")
            current = AppSettings(selected_style_id="classic_cross", accent_color="#ABCDEF")
            manager.save(current)

            preview = manager.preview_backup(current)
            self.assertTrue(preview["available"])
            self.assertEqual(preview["changedGroups"], ["Interface and appearance", "Crosshair and overlay"])
            self.assertNotIn("storagePath", preview["summary"])

            restored = manager.restore_backup(current, str(preview["fingerprint"]))

            self.assertEqual(restored.selected_style_id, "dot_micro")
            self.assertEqual(restored.accent_color, "#123456")
            self.assertEqual(json.loads(manager.settings_path.read_text(encoding="utf-8"))["selected_style_id"], "dot_micro")
            self.assertEqual(json.loads(manager.backup_path.read_text(encoding="utf-8"))["selected_style_id"], "classic_cross")

    def test_restore_refuses_backup_changed_after_preview(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            manager = self.make_manager(Path(tmp))
            current = AppSettings(selected_style_id="classic_cross")
            manager.settings_path.write_text(json.dumps(current.to_dict()), encoding="utf-8")
            manager.backup_path.write_text(json.dumps(AppSettings(selected_style_id="dot_micro").to_dict()), encoding="utf-8")
            preview = manager.preview_backup(current)
            manager.backup_path.write_text(json.dumps(AppSettings(selected_style_id="ring_micro").to_dict()), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "changed after preview"):
                manager.restore_backup(current, str(preview["fingerprint"]))
            self.assertEqual(json.loads(manager.settings_path.read_text(encoding="utf-8"))["selected_style_id"], "classic_cross")

    def test_boolean_strings_are_migrated_without_python_truthiness_bugs(self) -> None:
        settings = AppSettings.from_dict({"auto_update_on_startup": "false", "beta_zoom": {"live_enabled": "0"}})
        self.assertFalse(settings.auto_update_on_startup)
        self.assertFalse(settings.beta_zoom.live_enabled)

    def test_fire_cadence_is_bounded_and_migrates_to_press_only(self) -> None:
        migrated = AppSettings.from_dict({"reactive": {"fire_key_sequence": "CTRL+K"}, "game_profiles": [{"game_id": "g", "loadouts": [
            {"loadout_id": "l", "name": "Main", "style_id": "dot"}
        ]}]})
        self.assertEqual(migrated.reactive.fire_cadence_ms, 0)
        self.assertEqual(migrated.reactive.fire_key_sequence, "CTRL+K")
        self.assertEqual(migrated.game_profiles[0].loadouts[0].fire_cadence_ms, 0)
        bounded = AppSettings.from_dict({"reactive": {"fire_cadence_ms": 1500}})
        self.assertEqual(bounded.reactive.fire_cadence_ms, 1000)


if __name__ == "__main__":
    unittest.main()
