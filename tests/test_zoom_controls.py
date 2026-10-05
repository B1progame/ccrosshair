from __future__ import annotations

import unittest

from crosshair_overlay.app_settings import AppSettings
from crosshair_overlay.input_reactivity import FireInputTracker
from crosshair_overlay.zoom_controls import ZoomActivationLatch


class ZoomActivationTests(unittest.TestCase):
    def test_hold_mode_tracks_pressed_key_and_suppresses_typing(self):
        activation = ZoomActivationLatch()
        self.assertTrue(activation.update(True, True, False, "hold"))
        self.assertFalse(activation.update(True, True, True, "hold"))
        self.assertFalse(activation.update(False, True, False, "hold"))

    def test_toggle_mode_changes_only_on_a_non_typing_press_edge(self):
        activation = ZoomActivationLatch()
        self.assertFalse(activation.update(True, True, True, "toggle"))
        self.assertFalse(activation.update(True, True, False, "toggle"))
        self.assertFalse(activation.update(False, True, False, "toggle"))
        self.assertTrue(activation.update(True, True, False, "toggle"))
        self.assertTrue(activation.update(True, True, False, "toggle"))
        self.assertTrue(activation.update(False, True, False, "toggle"))
        self.assertFalse(activation.update(True, True, False, "toggle"))
        self.assertFalse(activation.update(True, True, False, "toggle"))

    def test_disabled_zoom_clears_toggle_state_and_legacy_settings_default_to_hold(self):
        activation = ZoomActivationLatch()
        activation.update(True, True, False, "toggle")
        activation.update(False, False, False, "toggle")
        self.assertFalse(activation.update(False, True, False, "toggle"))
        self.assertEqual(AppSettings.from_dict({"beta_zoom": {"activation_mode": "unknown"}}).beta_zoom.activation_mode, "hold")

    def test_mouse_and_optional_key_share_press_and_held_repeat_cadence(self):
        tracker = FireInputTracker()
        self.assertTrue(tracker.update(False, True, 10.0, 120))
        self.assertFalse(tracker.update(False, True, 10.1, 120))
        self.assertTrue(tracker.update(False, True, 10.13, 120))
        self.assertFalse(tracker.update(True, True, 10.14, 0))
        self.assertFalse(tracker.update(False, False, 10.15, 0))
        self.assertTrue(tracker.update(True, False, 10.16, 0))


if __name__ == "__main__":
    unittest.main()
