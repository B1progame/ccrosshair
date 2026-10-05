from __future__ import annotations

import unittest

from PySide6.QtGui import QColor, QImage

from crosshair_overlay.zoom_cleanup import reconstruct_center_mask


class ZoomCleanupTests(unittest.TestCase):
    def test_center_cleanup_preserves_unmasked_pixels_and_reduces_synthetic_error(self) -> None:
        clean = QImage(41, 41, QImage.Format.Format_RGB32)
        captured = QImage(41, 41, QImage.Format.Format_RGB32)
        for y in range(41):
            for x in range(41):
                color = QColor(40 + x * 2, 70 + y, 100)
                clean.setPixelColor(x, y, color)
                captured.setPixelColor(x, y, color)
        for offset in range(-4, 5):
            captured.setPixelColor(20 + offset, 20, QColor("white"))
            captured.setPixelColor(20, 20 + offset, QColor("white"))

        result = reconstruct_center_mask(captured, radius=5, strength=100)
        self.assertTrue(result.applied)
        masked_error_before = abs(captured.pixelColor(20, 20).red() - clean.pixelColor(20, 20).red())
        masked_error_after = abs(result.image.pixelColor(20, 20).red() - clean.pixelColor(20, 20).red())
        self.assertLess(masked_error_after, masked_error_before)
        for x, y in ((0, 0), (10, 20), (20, 10), (40, 40)):
            self.assertEqual(result.image.pixelColor(x, y), captured.pixelColor(x, y))

    def test_high_boundary_contrast_abstains_and_returns_source(self) -> None:
        image = QImage(31, 31, QImage.Format.Format_RGB32)
        image.fill(QColor("black"))
        for y in range(31):
            for x in range(16, 31):
                image.setPixelColor(x, y, QColor("white"))
        result = reconstruct_center_mask(image, radius=4, strength=100)
        self.assertFalse(result.applied)
        self.assertIs(result.image, image)

    def test_mask_preview_marks_boundary(self) -> None:
        image = QImage(31, 31, QImage.Format.Format_RGB32)
        image.fill(QColor("gray"))
        result = reconstruct_center_mask(image, radius=5, strength=100, preview=True)
        self.assertTrue(result.applied)
        self.assertNotEqual(result.image.pixelColor(15, 10), image.pixelColor(15, 10))


if __name__ == "__main__":
    unittest.main()
