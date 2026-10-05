from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QImage

from .zoom_cleanup import reconstruct_center_mask
from .zoom_ai import LocalSuperResolution


@dataclass(frozen=True)
class ZoomFrameJob:
    image: QImage
    output_size: tuple[int, int]
    generation: int
    mode: str
    captured_at: float
    cleanup_enabled: bool = False
    cleanup_radius: int = 5
    cleanup_strength: int = 100
    cleanup_preview: bool = False


class LatestFrameSlot:
    """A one-item mailbox: new captures replace work that has not started."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._job: ZoomFrameJob | None = None
        self._generation = 0
        self._closed = False
        self.dropped_frames = 0

    def submit(self, job: ZoomFrameJob) -> bool:
        with self._condition:
            if self._closed or job.generation != self._generation:
                return False
            if self._job is not None:
                self.dropped_frames += 1
            self._job = job
            self._condition.notify()
            return True

    def take(self) -> ZoomFrameJob | None:
        with self._condition:
            while self._job is None and not self._closed:
                self._condition.wait()
            if self._closed:
                return None
            job, self._job = self._job, None
            return job

    def set_generation(self, generation: int) -> None:
        with self._condition:
            self._generation = generation
            self._job = None

    def is_current(self, generation: int) -> bool:
        with self._condition:
            return not self._closed and generation == self._generation

    def has_newer_pending(self, job: ZoomFrameJob) -> bool:
        with self._condition:
            superseded = bool(
                self._job is not None
                and self._job.generation == job.generation
                and self._job.captured_at > job.captured_at
            )
            if superseded:
                self.dropped_frames += 1
            return superseded

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._job = None
            self._condition.notify_all()


class ZoomFrameProcessor(QThread):
    """Resize worker. QImage stays worker-safe; QPixmap is made by the GUI slot."""

    frame_ready = Signal(QImage, int, float, int)

    def __init__(self) -> None:
        super().__init__()
        self.slot = LatestFrameSlot()
        self._last_processing_ms = 0.0
        self._last_frame_age_ms = 0.0
        self._output_fps = 0.0
        self._last_output_at = 0.0
        self._frames_out = 0
        self._frame_ages: deque[float] = deque(maxlen=120)
        self._fps_samples: deque[float] = deque(maxlen=60)
        self._capture_size = (0, 0)
        self._mode = "balanced"
        self._cleanup_status = "disabled"
        self._cleanup_confidence = 0.0
        self._ai: LocalSuperResolution | None = None
        self._ai_error = ""
        self._ai_provider = ""

    @property
    def dropped_frames(self) -> int:
        return self.slot.dropped_frames

    @property
    def diagnostics(self) -> dict[str, float | int | str]:
        ages = sorted(self._frame_ages)

        def percentile(fraction: float) -> float:
            if not ages:
                return 0.0
            return ages[min(len(ages) - 1, round((len(ages) - 1) * fraction))]

        return {
            "backend": "Qt screen capture + worker resize",
            "model": (
                f"Super-Resolution 3x ({self._ai_provider})" if self._ai is not None
                else (f"unavailable: {self._ai_error}" if self._ai_error else "none (spatial interpolation)")
            ),
            "mode": self._mode,
            "captureWidth": self._capture_size[0],
            "captureHeight": self._capture_size[1],
            "processingMs": self._last_processing_ms,
            "frameAgeP50Ms": percentile(0.50),
            "frameAgeP95Ms": percentile(0.95),
            "outputFps": sum(self._fps_samples) / len(self._fps_samples) if self._fps_samples else self._output_fps,
            "droppedFrames": self.dropped_frames,
            "frames": self._frames_out,
            "cleanup": self._cleanup_status,
            "cleanupConfidence": self._cleanup_confidence,
        }

    def set_generation(self, generation: int) -> None:
        self.slot.set_generation(generation)

    def submit(self, image: QImage, output_size: tuple[int, int], generation: int, mode: str,
               cleanup_enabled: bool = False, cleanup_radius: int = 5,
               cleanup_strength: int = 100, cleanup_preview: bool = False) -> bool:
        if image.isNull():
            return False
        # Own the pixels before returning to the GUI event loop.
        return self.slot.submit(ZoomFrameJob(image.copy(), output_size, generation, mode, time.perf_counter(),
                                             cleanup_enabled, cleanup_radius, cleanup_strength, cleanup_preview))

    def stop(self) -> None:
        self.slot.close()
        if self.isRunning():
            self.wait(1500)

    def run(self) -> None:
        while True:
            job = self.slot.take()
            if job is None:
                return
            started = time.perf_counter()
            width, height = job.output_size
            self._capture_size = (job.image.width(), job.image.height())
            self._mode = job.mode
            source = job.image
            if job.cleanup_enabled:
                cleanup = reconstruct_center_mask(source, job.cleanup_radius, job.cleanup_strength, job.cleanup_preview)
                source = cleanup.image
                self._cleanup_confidence = cleanup.confidence
                self._cleanup_status = "applied" if cleanup.applied else "abstained (showing source)"
            else:
                self._cleanup_confidence = 0.0
                self._cleanup_status = "disabled"
            result = None
            if job.mode == "quality" and not self._ai_error:
                try:
                    if self._ai is None:
                        self._ai = LocalSuperResolution()
                        self._ai_provider = self._ai.provider
                    result = self._ai.enhance(source)
                except Exception as exc:  # noqa: BLE001
                    self._ai_error = type(exc).__name__
            if result is None:
                transform = QImage.TransformationMode.FastTransformation if job.mode == "fast" else QImage.TransformationMode.SmoothTransformation
                result = source.scaled(
                    max(1, width),
                    max(1, height),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    transform,
                )
            elif (result.width(), result.height()) != (max(1, width), max(1, height)):
                result = result.scaled(
                    max(1, width), max(1, height), Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            finished = time.perf_counter()
            if not self.slot.is_current(job.generation):
                continue
            if self.slot.has_newer_pending(job):
                continue
            self._last_processing_ms = (finished - started) * 1000
            self._last_frame_age_ms = (finished - job.captured_at) * 1000
            self._frame_ages.append(self._last_frame_age_ms)
            if self._last_output_at:
                delta = finished - self._last_output_at
                if delta > 0:
                    self._output_fps = 1.0 / delta
                    self._fps_samples.append(self._output_fps)
            self._last_output_at = finished
            self._frames_out += 1
            self.frame_ready.emit(result, job.generation, job.captured_at, self.dropped_frames)
