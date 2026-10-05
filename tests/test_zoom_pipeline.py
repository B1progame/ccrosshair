from __future__ import annotations

import unittest

from PySide6.QtGui import QImage

from crosshair_overlay.zoom_pipeline import LatestFrameSlot, ZoomFrameJob


class LatestFrameSlotTests(unittest.TestCase):
    def job(self, marker: int, generation: int = 1) -> ZoomFrameJob:
        image = QImage(2, 2, QImage.Format.Format_ARGB32)
        image.fill(marker)
        return ZoomFrameJob(image, (4, 4), generation, "fast", float(marker))

    def test_pending_capture_is_replaced_and_queue_stays_bounded(self) -> None:
        slot = LatestFrameSlot()
        slot.set_generation(1)
        self.assertTrue(slot.submit(self.job(1)))
        self.assertTrue(slot.submit(self.job(2)))
        self.assertTrue(slot.submit(self.job(3)))
        self.assertEqual(slot.dropped_frames, 2)
        latest = slot.take()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.captured_at, 3.0)
        slot.close()

    def test_old_session_frames_are_rejected_after_cancel(self) -> None:
        slot = LatestFrameSlot()
        slot.set_generation(4)
        self.assertTrue(slot.submit(self.job(1, generation=4)))
        slot.set_generation(5)
        self.assertFalse(slot.submit(self.job(2, generation=4)))
        self.assertTrue(slot.is_current(5))
        self.assertFalse(slot.is_current(4))
        slot.close()


if __name__ == "__main__":
    unittest.main()
