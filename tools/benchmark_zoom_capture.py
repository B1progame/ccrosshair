"""Measure current Qt desktop crop capture and worker-equivalent image scaling."""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import time
import winreg

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def gpu_name() -> str:
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


def main() -> None:
    app = QGuiApplication([])
    screen = app.primaryScreen()
    if screen is None:
        raise SystemExit("No Qt desktop screen is available for capture.")
    geometry = screen.geometry()
    crop_width, crop_height = min(320, geometry.width()), min(180, geometry.height())
    x = geometry.x() + (geometry.width() - crop_width) // 2
    y = geometry.y() + (geometry.height() - crop_height) // 2
    samples = 180
    modes = {
        "fast": Qt.TransformationMode.FastTransformation,
        "smooth": Qt.TransformationMode.SmoothTransformation,
    }
    results = []
    for mode, transformation in modes.items():
        capture_ms: list[float] = []
        resize_ms: list[float] = []
        total_ms: list[float] = []
        for index in range(samples + 10):
            started = time.perf_counter()
            pixmap = screen.grabWindow(0, x, y, crop_width, crop_height)
            captured = time.perf_counter()
            image = pixmap.toImage()
            if image.isNull():
                raise SystemExit("Qt returned an empty desktop capture; benchmark is unavailable.")
            image.scaled(1280, 720, Qt.AspectRatioMode.IgnoreAspectRatio, transformation)
            finished = time.perf_counter()
            if index >= 10:
                capture_ms.append((captured - started) * 1000)
                resize_ms.append((finished - captured) * 1000)
                total_ms.append((finished - started) * 1000)
        results.append({
            "mode": mode,
            "capture_ms_p50": round(percentile(capture_ms, 0.5), 3),
            "capture_ms_p95": round(percentile(capture_ms, 0.95), 3),
            "resize_ms_p50": round(percentile(resize_ms, 0.5), 3),
            "resize_ms_p95": round(percentile(resize_ms, 0.95), 3),
            "total_ms_p50": round(percentile(total_ms, 0.5), 3),
            "total_ms_p95": round(percentile(total_ms, 0.95), 3),
            "serial_samples_per_second": round(1000 / statistics.mean(total_ms), 2),
        })
    print(json.dumps({
        "hardware": {"cpu": cpu_name(), "gpu": gpu_name()},
        "os": platform.platform(),
        "capture_backend": "QScreen.grabWindow(0)",
        "capture_crop": [crop_width, crop_height],
        "output_size": [1280, 720],
        "warmup_frames_per_mode": 10,
        "measured_frames_per_mode": samples,
        "scope": "desktop crop capture plus QImage scaling; excludes a running game, overlay presentation, and AI inference",
        "results": results,
    }, indent=2))
    app.quit()


if __name__ == "__main__":
    main()
