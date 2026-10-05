"""Measure the bundled ONNX model and compare it to smooth scaling."""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import time
import winreg

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

from crosshair_overlay.zoom_ai import INPUT_SIDE, MODEL_SHA256, LocalSuperResolution


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def gpu_info() -> str:
    try:
        return subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            check=True, capture_output=True, text=True, timeout=3,
        ).stdout.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "not reported by nvidia-smi"


def cpu_name() -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    except OSError:
        return platform.processor() or platform.machine()


def pixels(image: QImage) -> np.ndarray:
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    rows = np.frombuffer(bytes(rgb.constBits()), dtype=np.uint8).reshape(rgb.height(), rgb.bytesPerLine())
    return rows[:, :rgb.width() * 3].reshape(rgb.height(), rgb.width(), 3).astype(np.float32)


def quality_metrics(image: QImage, reference: QImage) -> dict[str, float]:
    difference = pixels(image) - pixels(reference)
    mse = float(np.mean(difference * difference))
    return {
        "mae_rgb": round(float(np.mean(np.abs(difference))), 4),
        "psnr_db": round(float(10 * np.log10(255**2 / max(mse, 1e-12))), 4),
    }


def main() -> None:
    model = LocalSuperResolution()
    sample = QImage(320, 320, QImage.Format.Format_RGB32)
    sample.fill(QColor("#506477"))
    painter = QPainter(sample)
    painter.setPen(QPen(QColor("#94a6ad"), 2))
    for offset in range(0, 320, 32):
        painter.drawLine(offset, 0, offset, 319)
        painter.drawLine(0, offset, 319, offset)
    painter.setPen(QPen(QColor("#ffffff"), 3))
    painter.drawLine(128, 160, 192, 160)
    painter.drawLine(160, 128, 160, 192)
    painter.end()
    for _ in range(15):
        model.enhance(sample)
    latency_ms = []
    for _ in range(120):
        started = time.perf_counter()
        model.enhance(sample)
        latency_ms.append((time.perf_counter() - started) * 1000)

    reference = QImage(672, 672, QImage.Format.Format_RGB32)
    reference.fill(QColor("#2a373f"))
    painter = QPainter(reference)
    painter.setPen(QPen(QColor("#aab9be"), 2))
    for offset in range(0, 672, 48):
        painter.drawLine(offset, 0, offset, 671)
        painter.drawLine(0, offset, 671, offset)
    painter.setPen(QPen(QColor("#fafafa"), 4))
    painter.drawLine(280, 336, 392, 336)
    painter.drawLine(336, 280, 336, 392)
    painter.end()
    low = reference.scaled(INPUT_SIDE, INPUT_SIDE, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    sr = model.enhance(low)
    baseline = low.scaled(672, 672, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)

    print(json.dumps({
        "hardware": {"cpu": cpu_name(), "gpu": gpu_info()},
        "os": platform.platform(),
        "model_sha256": MODEL_SHA256,
        "provider": model.provider,
        "source_crop": [320, 320],
        "model_input": [INPUT_SIDE, INPUT_SIDE],
        "output": [672, 672],
        "warmup_frames": 15,
        "measured_frames": len(latency_ms),
        "inference_and_conversion_ms": {
            "p50": round(percentile(latency_ms, 0.50), 3),
            "p95": round(percentile(latency_ms, 0.95), 3),
            "serial_fps": round(1000 / statistics.mean(latency_ms), 2),
        },
        "synthetic_reference_rgb_metrics": {
            "smooth_scaling": quality_metrics(baseline, reference),
            "onnx_super_resolution": quality_metrics(sr, reference),
            "caveat": "single synthetic grid/reticle image; not a general or gameplay quality claim",
        },
    }, indent=2))


if __name__ == "__main__":
    main()
