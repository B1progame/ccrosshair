from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from .config import OverlayStyle
from .input_reactivity import pulse_envelope
from .overlay_renderer import draw_overlay_style


class CrosshairWidget(QWidget):
    """Paints the currently selected overlay style."""

    def __init__(self, style: OverlayStyle, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayCrosshair")
        self._style = style
        self._pulse_started = 0.0
        self._pulse_duration_ms = 120
        self._pulse_amplitude = 0
        self._opacity_pulse = False
        self._gap_expansion = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(16)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._apply_size()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_style(self, style: OverlayStyle) -> bool:
        if style == self._style:
            return False
        self._style = style
        self._apply_size()
        self.update()
        return True

    def _apply_size(self) -> None:
        # Keep spare transparent paint area so an input pulse never clips the
        # crosshair while preserving the exact window center.
        size = self._style.canvas_size * 2 + 1
        self.setFixedSize(size, size)

    def trigger_fire_pulse(self, duration_ms: int, amplitude_percent: int, opacity_pulse: bool, gap_expansion: bool = True) -> None:
        self._pulse_started = time.perf_counter()
        self._pulse_duration_ms = max(40, int(duration_ms))
        self._pulse_amplitude = max(0, min(100, int(amplitude_percent)))
        self._opacity_pulse = bool(opacity_pulse)
        self._gap_expansion = bool(gap_expansion)
        self._pulse_timer.start()
        self.update()

    def _update_pulse(self) -> None:
        if (time.perf_counter() - self._pulse_started) * 1000.0 >= self._pulse_duration_ms:
            self._pulse_timer.stop()
        self.update()

    def cancel_fire_pulse(self) -> None:
        self._pulse_timer.stop()
        self._pulse_started = 0.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        elapsed = (time.perf_counter() - self._pulse_started) * 1000.0 if self._pulse_started else self._pulse_duration_ms
        pulse = pulse_envelope(elapsed, self._pulse_duration_ms)
        center = self.rect().center()
        painter.translate(center)
        painter.scale(1.0 + self._pulse_amplitude * pulse / 100.0, 1.0 + self._pulse_amplitude * pulse / 100.0)
        painter.translate(-center)
        if self._opacity_pulse:
            painter.setOpacity(1.0 - 0.35 * pulse)
        paint_style = self._style
        if self._gap_expansion and pulse and self._pulse_amplitude:
            paint_style = replace(self._style, gap=self._style.gap + round(max(2, self._pulse_amplitude / 3) * pulse))
        draw_overlay_style(painter, self.rect(), paint_style)
