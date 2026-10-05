from __future__ import annotations

import unittest

from crosshair_overlay.app_settings import AppSettings
from crosshair_overlay.crosshairs.catalog import build_builtin_catalog
from crosshair_overlay.crosshairs.io import definition_from_dict, definition_to_dict
from crosshair_overlay.input_reactivity import pulse_envelope
from crosshair_overlay.zoom_controls import effective_zoom_max_percent, stepped_zoom_percent


class CatalogFeatureTests(unittest.TestCase):
    def test_offline_catalog_has_one_hundred_distinct_geometries(self) -> None:
        catalog = build_builtin_catalog()
        geometries = {
            (item.style.shape, item.style.arm_length, item.style.gap, item.style.thickness,
             item.style.center_dot, item.style.center_dot_size, item.style.circle_radius,
             item.style.circle_thickness, item.style.t_style, item.style.outline_enabled)
            for item in catalog.values()
        }
        self.assertGreaterEqual(len(catalog), 100)
        self.assertEqual(len(catalog), len(geometries))
        self.assertTrue(any(item.style.shape.value == "chevron" for item in catalog.values()))
        self.assertTrue(any(item.style.shape.value == "sniper" for item in catalog.values()))

    def test_original_preset_metadata_and_appearance_round_trip(self) -> None:
        source = build_builtin_catalog()["classic_cross"]
        payload = definition_to_dict(source)
        restored = definition_from_dict(payload)
        self.assertEqual(restored.source_url, source.source_url)
        self.assertEqual(restored.reuse_status, "original pattern; not a copied game asset")
        self.assertEqual(restored.style.color_rgba, source.style.color_rgba)
        self.assertEqual(restored.style.outline_rgba, source.style.outline_rgba)

    def test_malformed_metadata_is_rejected(self) -> None:
        payload = definition_to_dict(build_builtin_catalog()["classic_cross"])
        payload["aliases"] = "not a list"
        with self.assertRaises(ValueError):
            definition_from_dict(payload)

    def test_new_preferences_migrate_and_validate(self) -> None:
        settings = AppSettings.from_dict({
            "accessibility": {"density": "dense", "text_scale": 800},
            "reactive": {"enabled": "true", "fire_amplitude_percent": 200},
            "recent_crosshair_colors": ["#12ABEF", "red", "#12abef"],
            "beta_zoom": {"cleanup_enabled": "true", "cleanup_radius": 99, "cleanup_strength": -3},
        })
        self.assertEqual(settings.accessibility.density, "comfortable")
        self.assertEqual(settings.accessibility.text_scale, 150)
        self.assertTrue(settings.reactive.enabled)
        self.assertEqual(settings.reactive.fire_amplitude_percent, 100)
        self.assertEqual(settings.recent_crosshair_colors, ["#12ABEF"])
        self.assertTrue(settings.beta_zoom.cleanup_enabled)
        self.assertEqual(settings.beta_zoom.cleanup_radius, 24)
        self.assertEqual(settings.beta_zoom.cleanup_strength, 0)

    def test_legacy_game_profiles_migrate_to_named_loadouts(self) -> None:
        settings = AppSettings.from_dict({"game_profiles": [
            {"game_id": "legacy", "title": "Legacy", "source": "manual", "style_id": "classic_cross", "enabled": True},
            {"game_id": "modern", "title": "Modern", "source": "manual", "style_id": "old",
             "loadouts": [{"loadout_id": "hip", "name": "Hip fire", "style_id": "dot_micro",
                            "zoom_percent": 9000, "fire_amplitude_percent": -3}], "active_loadout_id": "hip"},
        ]})
        legacy, modern = settings.game_profiles
        self.assertEqual(legacy.loadouts[0].loadout_id, "default")
        self.assertEqual(legacy.loadouts[0].style_id, "classic_cross")
        self.assertEqual(modern.style_id, "dot_micro")
        self.assertEqual(modern.loadouts[0].zoom_percent, 1600)
        self.assertEqual(modern.loadouts[0].fire_amplitude_percent, 0)
        round_trip = AppSettings.from_dict(settings.to_dict())
        self.assertEqual(round_trip.game_profiles[1].active_loadout_id, "hip")

    def test_input_pulse_uses_elapsed_time_and_recovers(self) -> None:
        self.assertEqual(pulse_envelope(-10, 120), 0.0)
        self.assertAlmostEqual(pulse_envelope(60, 120), 1.0)
        self.assertAlmostEqual(pulse_envelope(120, 120), 0.0)

    def test_wheel_zoom_steps_respect_effective_bounds(self) -> None:
        self.assertEqual(stepped_zoom_percent(200, -120), 200)
        self.assertEqual(stepped_zoom_percent(200, 120), 225)
        self.assertEqual(stepped_zoom_percent(1600, 120), 1600)
        self.assertEqual(stepped_zoom_percent(600, 0), 600)

    def test_effective_zoom_max_uses_source_crop_floor_and_global_cap(self) -> None:
        self.assertEqual(effective_zoom_max_percent(320, 1920), 200)
        self.assertEqual(effective_zoom_max_percent(320, 40), 800)
        self.assertEqual(effective_zoom_max_percent(320, 10), 1600)


if __name__ == "__main__":
    unittest.main()
