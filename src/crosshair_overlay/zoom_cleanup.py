from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen


@dataclass(frozen=True)
class CleanupResult:
    image: QImage
    confidence: float
    applied: bool


def reconstruct_center_mask(image: QImage, radius: int, strength: int, preview: bool = False) -> CleanupResult:
    """Interpolate a manually sized center mask for Zoom preview only.

    Pixels outside the circular mask remain byte-for-byte unchanged. Large
    boundary disagreement makes the function abstain and return the source.
    It cannot recover pixels hidden by the game's crosshair.
    """
    if image.isNull() or radius < 1 or image.width() < radius * 2 + 2 or image.height() < radius * 2 + 2:
        return CleanupResult(image, 0.0, False)

    cx, cy = image.width() // 2, image.height() // 2
    radius = min(int(radius), cx - 1, cy - 1)
    if radius < 1:
        return CleanupResult(image, 0.0, False)

    left = image.pixelColor(cx - radius - 1, cy)
    right = image.pixelColor(cx + radius + 1, cy)
    boundary_delta = max(abs(left.red() - right.red()), abs(left.green() - right.green()), abs(left.blue() - right.blue()))
    confidence = max(0.0, 1.0 - boundary_delta / 160.0)
    if confidence < 0.15:
        return CleanupResult(_draw_mask_boundary(image, cx, cy, radius) if preview else image, confidence, False)

    result = image.copy()
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setClipPath(_circle_path(cx, cy, radius))
    opacity = max(0, min(100, int(strength))) / 100.0
    for y in range(cy - radius, cy + radius + 1):
        half = int((max(0, radius * radius - (y - cy) * (y - cy))) ** 0.5)
        y_left = image.pixelColor(cx - half - 1, y)
        y_right = image.pixelColor(cx + half + 1, y)
        gradient = QLinearGradient(cx - half, y, cx + half, y)
        gradient.setColorAt(0.0, y_left)
        gradient.setColorAt(1.0, y_right)
        painter.setOpacity(opacity)
        painter.fillRect(QRectF(cx - half, y, 2 * half + 1, 1), gradient)
    painter.setClipping(False)
    painter.end()
    if preview:
        result = _draw_mask_boundary(result, cx, cy, radius)
    return CleanupResult(result, confidence, True)


def _circle_path(cx: int, cy: int, radius: int):
    from PySide6.QtGui import QPainterPath

    path = QPainterPath()
    path.addEllipse(QRectF(cx - radius, cy - radius, 2 * radius + 1, 2 * radius + 1))
    return path


def _draw_mask_boundary(image: QImage, cx: int, cy: int, radius: int) -> QImage:
    result = image.copy()
    painter = QPainter(result)
    painter.setPen(QPen(QColor(255, 70, 210, 230), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius))
    painter.end()
    return result
