from __future__ import annotations

import unittest

from crosshair_overlay.compatibility_check import probe_screen_capture


class CompatibilityCheckTests(unittest.TestCase):
    def test_probe_captures_and_discards_only_a_two_pixel_sample(self) -> None:
        class Geometry:
            def x(self): return -1920
            def y(self): return 0
            def width(self): return 1920
            def height(self): return 1080

        class Image:
            def isNull(self): return False

        class Screen:
            def geometry(self): return Geometry()
            def devicePixelRatio(self): return 1.25
            def grabWindow(self, window, x, y, width, height):
                self.sample = (window, x, y, width, height)
                return Image()

        screen = Screen()
        report = probe_screen_capture(screen, 1)
        self.assertEqual(screen.sample, (0, 960, 540, 2, 2))
        self.assertTrue(report["captureAvailable"])
        self.assertEqual((report["x"], report["devicePixelRatio"], report["display"]), (-1920, 1.25, "Display 2"))
        self.assertNotIn("image", report)

    def test_capture_denial_is_reported_without_propagating_error_details(self) -> None:
        class Geometry:
            def x(self): return 0
            def y(self): return 0
            def width(self): return 10
            def height(self): return 10

        class Screen:
            def geometry(self): return Geometry()
            def devicePixelRatio(self): return 1
            def grabWindow(self, *args): raise PermissionError("private display diagnostic detail")

        report = probe_screen_capture(Screen(), 0)
        self.assertFalse(report["captureAvailable"])
        self.assertIn("PermissionError", report["status"])
        self.assertNotIn("private display", report["status"])


if __name__ == "__main__":
    unittest.main()
