from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from crosshair_overlay.zoom_ai import LocalSuperResolution, MODEL_SHA256
from crosshair_overlay.zoom_pipeline import ZoomFrameProcessor


class ZoomAiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_model_hash_and_local_inference_produce_three_x_qimage(self) -> None:
        model = LocalSuperResolution()
        image = QImage(256, 256, QImage.Format.Format_RGB32)
        image.fill(QColor("#65788a"))
        result = model.enhance(image)
        self.assertIn(model.provider, {"DmlExecutionProvider", "CPUExecutionProvider"})
        self.assertEqual((result.width(), result.height()), (672, 672))
        self.assertFalse(result.isNull())
        self.assertEqual(len(MODEL_SHA256), 64)

    def test_quality_mode_runs_in_worker_and_reports_provider(self) -> None:
        processor = ZoomFrameProcessor()
        processor.set_generation(1)
        loop = QEventLoop()
        frames = []

        def received(image: QImage, generation: int, captured_at: float, dropped: int) -> None:
            frames.append((image, generation, captured_at, dropped))
            loop.quit()

        processor.frame_ready.connect(received)
        processor.start()
        image = QImage(256, 256, QImage.Format.Format_RGB32)
        image.fill(QColor("#607080"))
        try:
            self.assertTrue(processor.submit(image, (300, 300), 1, "quality"))
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
        finally:
            processor.stop()
        self.assertEqual(len(frames), 1)
        self.assertEqual((frames[0][0].width(), frames[0][0].height()), (300, 300))
        self.assertEqual(frames[0][1], 1)
        self.assertIn("Super-Resolution 3x", processor.diagnostics["model"])


if __name__ == "__main__":
    unittest.main()
