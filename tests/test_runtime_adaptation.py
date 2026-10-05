import unittest
from types import SimpleNamespace

from crosshair_overlay.app_settings import AppSettings, BetaZoomSettings
from crosshair_overlay.app import AppController
from crosshair_overlay.runtime_adaptation import GpuRuntimeAdaptation


class GpuRuntimeAdaptationTests(unittest.TestCase):
    def test_three_hot_samples_reduce_mode_and_six_cool_samples_restore(self):
        adaptation = GpuRuntimeAdaptation()
        for _ in range(2):
            self.assertEqual(adaptation.sample("quality", 87, 60), "quality")
        self.assertEqual(adaptation.sample("quality", 87, 60), "eco")
        for _ in range(5):
            self.assertEqual(adaptation.sample("quality", 65, 40), "eco")
        self.assertEqual(adaptation.sample("quality", 65, 40), "quality")

    def test_manual_mode_is_never_overridden_for_low_activity_modes(self):
        adaptation = GpuRuntimeAdaptation()
        for _ in range(4):
            self.assertEqual(adaptation.sample("eco", 95, 99), "eco")
        self.assertIsNone(adaptation.override)
        self.assertIn("already low activity", adaptation.status)

    def test_midrange_sample_resets_hysteresis_without_losing_override(self):
        adaptation = GpuRuntimeAdaptation()
        for _ in range(3):
            adaptation.sample("balanced", 90, 70)
        self.assertEqual(adaptation.sample("balanced", 80, 90), "eco")
        for _ in range(5):
            self.assertEqual(adaptation.sample("balanced", 70, 60), "eco")
        self.assertEqual(adaptation.sample("balanced", 70, 60), "balanced")

    def test_setting_defaults_off_and_round_trips(self):
        defaults = BetaZoomSettings()
        self.assertFalse(defaults.auto_adapt_enabled)
        enabled = AppSettings.from_dict({"beta_zoom": {"auto_adapt_enabled": True}})
        self.assertTrue(enabled.beta_zoom.auto_adapt_enabled)

    def test_runtime_mode_normalization_preserves_adaptation_and_sidebar(self):
        controller = SimpleNamespace(_settings=AppSettings(
            beta_zoom=BetaZoomSettings(sidebar_enabled=True)
        ))
        normalized = AppController._normalized_beta_zoom_settings(
            controller, BetaZoomSettings(auto_adapt_enabled=True, runtime_mode="quality")
        )
        self.assertTrue(normalized.auto_adapt_enabled)
        self.assertTrue(normalized.sidebar_enabled)
        self.assertEqual(normalized.runtime_mode, "quality")


if __name__ == "__main__":
    unittest.main()
