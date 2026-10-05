from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

MODEL_FILENAME = "super-resolution-10.onnx"
MODEL_SHA256 = "85f36ff88cc504a24af5e0602148bc56a8aa09a58eca8c0da2756f3e8186035e"
MODEL_URL = "https://huggingface.co/onnxmodelzoo/super-resolution-10"
INPUT_SIDE = 224
OUTPUT_SIDE = 672


def model_path() -> Path:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return root / "crosshair_overlay" / "assets" / "models" / MODEL_FILENAME
    return Path(__file__).resolve().parent / "assets" / "models" / MODEL_FILENAME


class LocalSuperResolution:
    """Lazy, checksum-verified 3x ONNX upscaler; called only by the zoom worker."""

    def __init__(self) -> None:
        import numpy as np
        import onnxruntime as ort

        path = model_path()
        if not path.is_file():
            raise FileNotFoundError(f"Local model is missing: {path.name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != MODEL_SHA256:
            raise ValueError("The local super-resolution model checksum does not match its manifest.")

        self.np = np
        options = ort.SessionOptions()
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_mem_pattern = False
        options.log_severity_level = 3
        providers = ort.get_available_providers()
        requested = ["DmlExecutionProvider", "CPUExecutionProvider"] if "DmlExecutionProvider" in providers else ["CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(str(path), sess_options=options, providers=requested)
        except Exception:
            self.session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
        self.provider = self.session.get_providers()[0]
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self._to_ycbcr = np.asarray(
            [[0.299, 0.587, 0.114], [-0.168736, -0.331264, 0.5], [0.5, -0.418688, -0.081312]],
            dtype=np.float32,
        )
        self._from_ycbcr = np.asarray(
            [[1.0, 0.0, 1.402], [1.0, -0.344136, -0.714136], [1.0, 1.772, 0.0]],
            dtype=np.float32,
        )
        self.session.run(
            [self.output_name],
            {self.input_name: np.zeros((1, 1, INPUT_SIDE, INPUT_SIDE), dtype=np.float32)},
        )

    def enhance(self, source: QImage) -> QImage:
        np = self.np
        rgb = source.scaled(
            INPUT_SIDE, INPUT_SIDE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ).convertToFormat(QImage.Format.Format_RGB888)
        stride = rgb.bytesPerLine()
        rows = np.frombuffer(bytes(rgb.constBits()), dtype=np.uint8).reshape(INPUT_SIDE, stride)
        pixels = rows[:, :INPUT_SIDE * 3].reshape(INPUT_SIDE, INPUT_SIDE, 3).astype(np.float32)
        ycbcr = pixels @ self._to_ycbcr.T
        ycbcr[:, :, 1:] += 128.0
        tensor = np.ascontiguousarray(ycbcr[:, :, 0][None, None, :, :] / 255.0, dtype=np.float32)
        upscaled_y = self.session.run([self.output_name], {self.input_name: tensor})[0]
        y_plane = np.clip(np.rint(upscaled_y[0, 0] * 255.0), 0, 255).astype(np.uint8)

        def scaled_chroma(channel: int) -> np.ndarray:
            raw = np.clip(np.rint(ycbcr[:, :, channel]), 0, 255).astype(np.uint8).tobytes()
            plane = QImage(raw, INPUT_SIDE, INPUT_SIDE, INPUT_SIDE, QImage.Format.Format_Grayscale8).copy()
            scaled = plane.scaled(OUTPUT_SIDE, OUTPUT_SIDE, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            return np.frombuffer(bytes(scaled.constBits()), dtype=np.uint8).reshape(
                OUTPUT_SIDE, scaled.bytesPerLine()
            )[:, :OUTPUT_SIDE].astype(np.float32)

        chroma = np.stack((scaled_chroma(1), scaled_chroma(2)), axis=2) - 128.0
        components = np.concatenate((y_plane.astype(np.float32)[:, :, None], chroma), axis=2)
        result = np.clip(np.rint(components @ self._from_ycbcr.T), 0, 255).astype(np.uint8)
        return QImage(result.data, OUTPUT_SIDE, OUTPUT_SIDE, OUTPUT_SIDE * 3,
                      QImage.Format.Format_RGB888).copy()
