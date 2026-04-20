from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .config import OverlayShape, OverlayStyle


def draw_overlay_style(painter: QPainter, target_rect: QRect | QRectF, style: OverlayStyle) -> None:
    rectf = QRectF(target_rect)
    centerf = QPointF(rectf.left() + (rectf.width() / 2.0), rectf.top() + (rectf.height() / 2.0))
    color = QColor(*style.color_rgba)
    outline = QColor(*style.outline_rgba)

    painter.save()
    if abs(style.rotation_degrees) > 0.01:
        painter.translate(centerf)
        painter.rotate(style.rotation_degrees)
        painter.translate(-centerf)

    if style.outline_enabled:
        _draw_shape(painter, centerf, style, outline_mode=True, color=outline)
    _draw_shape(painter, centerf, style, outline_mode=False, color=color)
    painter.restore()


def _draw_shape(painter: QPainter, center: QPointF, style: OverlayStyle, outline_mode: bool, color: QColor) -> None:
    line_thickness = style.thickness + (style.outline_thickness * 2 if outline_mode else 0)
    circle_thickness = style.circle_thickness + (style.outline_thickness * 2 if outline_mode else 0)
    dot_size = style.center_dot_size + (style.outline_thickness * 2 if outline_mode else 0)

    if style.shape in (OverlayShape.CLASSIC_CROSS, OverlayShape.CIRCLE_CROSS):
        _draw_classic_cross(painter, center, style, color, line_thickness)

    if style.shape == OverlayShape.CIRCLE_CROSS:
        _draw_ring(painter, center, style.circle_radius, color, circle_thickness)

    if style.shape == OverlayShape.RING:
        _draw_ring(painter, center, style.circle_radius, color, circle_thickness)

    if style.shape == OverlayShape.BRACKET:
        _draw_bracket(painter, center, style, color, line_thickness)

    if style.shape == OverlayShape.SQUARE:
        _draw_square(painter, center, style, color, line_thickness)

    if style.shape == OverlayShape.DIAMOND:
        _draw_diamond(painter, center, style, color, line_thickness)

    if style.shape == OverlayShape.CUSTOM_GRID:
        _draw_custom_grid(painter, center, style, color)

    if style.center_dot or style.shape == OverlayShape.DOT:
        half = dot_size / 2.0
        rect = QRectF(center.x() - half, center.y() - half, float(dot_size), float(dot_size))
        painter.fillRect(rect, color)


def _draw_classic_cross(painter: QPainter, center: QPointF, style: OverlayStyle, color: QColor, thickness: int) -> None:
    pen = QPen(color, max(1, thickness))
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter.setPen(pen)

    half_gap = style.gap / 2.0
    arm = float(style.arm_length)
    cx = center.x()
    cy = center.y()

    painter.drawLine(cx - half_gap - arm, cy, cx - half_gap, cy)
    painter.drawLine(cx + half_gap, cy, cx + half_gap + arm, cy)
    if not style.t_style:
        painter.drawLine(cx, cy - half_gap - arm, cx, cy - half_gap)
    painter.drawLine(cx, cy + half_gap, cx, cy + half_gap + arm)


def _draw_ring(painter: QPainter, center: QPointF, radius: int, color: QColor, thickness: int) -> None:
    pen = QPen(color, max(1, thickness))
    painter.setPen(pen)
    diameter = radius * 2
    painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, diameter, diameter))


def _draw_bracket(painter: QPainter, center: QPointF, style: OverlayStyle, color: QColor, thickness: int) -> None:
    pen = QPen(color, max(1, thickness))
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter.setPen(pen)

    half_gap = style.gap / 2.0
    arm = float(style.arm_length)
    cx = center.x()
    cy = center.y()

    left = cx - half_gap
    right = cx + half_gap
    top = cy - half_gap
    bottom = cy + half_gap

    painter.drawLine(left - arm, top, left, top)
    painter.drawLine(left, top - arm, left, top)

    painter.drawLine(right, top, right + arm, top)
    painter.drawLine(right, top - arm, right, top)

    painter.drawLine(left - arm, bottom, left, bottom)
    painter.drawLine(left, bottom, left, bottom + arm)

    painter.drawLine(right, bottom, right + arm, bottom)
    painter.drawLine(right, bottom, right, bottom + arm)


def _draw_square(painter: QPainter, center: QPointF, style: OverlayStyle, color: QColor, thickness: int) -> None:
    pen = QPen(color, max(1, thickness))
    painter.setPen(pen)
    half = max(2.0, style.gap / 2.0 + style.arm_length / 2.0)
    rect = QRectF(center.x() - half, center.y() - half, half * 2.0, half * 2.0)
    painter.drawRect(rect)


def _draw_diamond(painter: QPainter, center: QPointF, style: OverlayStyle, color: QColor, thickness: int) -> None:
    pen = QPen(color, max(1, thickness))
    painter.setPen(pen)
    half_w = max(2.0, style.arm_length / 2.0 + style.gap / 3.0)
    points = [
        QPointF(center.x(), center.y() - half_w),
        QPointF(center.x() + half_w, center.y()),
        QPointF(center.x(), center.y() + half_w),
        QPointF(center.x() - half_w, center.y()),
    ]
    for idx in range(len(points)):
        painter.drawLine(points[idx], points[(idx + 1) % len(points)])


def _draw_custom_grid(painter: QPainter, center: QPointF, style: OverlayStyle, color: QColor) -> None:
    cell_size = max(1, style.custom_cell_size)
    grid_size = max(8, style.custom_grid_size)
    grid_px = grid_size * cell_size
    left = center.x() - (grid_px / 2.0)
    top = center.y() - (grid_px / 2.0)
    for x, y in style.custom_filled_cells:
        painter.fillRect(QRectF(left + (x * cell_size), top + (y * cell_size), cell_size, cell_size), color)


def _rotated_point(center: QPointF, x: float, y: float, degrees: float) -> QPointF:
    if abs(degrees) <= 0.01:
        return QPointF(x, y)
    rad = math.radians(degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    tx = x - center.x()
    ty = y - center.y()
    return QPointF(center.x() + (tx * cos_a) - (ty * sin_a), center.y() + (tx * sin_a) + (ty * cos_a))
