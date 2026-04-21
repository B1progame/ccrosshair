from __future__ import annotations

import re

from PySide6.QtGui import QColor
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter

from ..config import OverlayShape, OverlayStyle
from ..overlay_renderer import draw_overlay_style
from .models import CreatorCrosshair


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip().lower())
    slug = slug.strip("_")
    return slug or "custom_crosshair"


def creator_to_overlay_style(model: CreatorCrosshair, style_id: str | None = None) -> OverlayStyle:
    color = QColor(model.color_hex)
    if not color.isValid():
        color = QColor("#FFFFFF")

    cells = tuple((int(x), int(y)) for x, y in model.normalized_cells())
    resolved_style_id = style_id or model.style_id or slugify_name(model.name)
    cell_size = max(1, min(4, int(round(32 / max(16, model.grid_size)))))
    return OverlayStyle(
        style_id=resolved_style_id,
        display_name=model.name or "Custom Crosshair",
        shape=OverlayShape.CUSTOM_GRID,
        thickness=1,
        color_rgba=(color.red(), color.green(), color.blue(), 255),
        center_dot=False,
        center_dot_size=1,
        custom_grid_size=model.grid_size,
        custom_filled_cells=cells,
        custom_cell_size=cell_size,
    )


def overlay_style_to_creator(model_name: str, style: OverlayStyle, grid_size: int = 32) -> CreatorCrosshair:
    bounded_grid = max(16, min(64, int(grid_size)))
    canvas_size = 320
    image = QImage(canvas_size, canvas_size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    monochrome = OverlayStyle(
        style_id=style.style_id,
        display_name=style.display_name,
        shape=style.shape,
        arm_length=style.arm_length,
        gap=style.gap,
        thickness=style.thickness,
        color_rgba=(255, 255, 255, 255),
        center_dot=style.center_dot,
        center_dot_size=style.center_dot_size,
        circle_radius=style.circle_radius,
        circle_thickness=style.circle_thickness,
        custom_grid_size=style.custom_grid_size,
        custom_filled_cells=style.custom_filled_cells,
        custom_cell_size=style.custom_cell_size,
        t_style=style.t_style,
        outline_enabled=style.outline_enabled,
        outline_thickness=style.outline_thickness,
        outline_rgba=(255, 255, 255, 255),
        rotation_degrees=style.rotation_degrees,
    )
    draw_overlay_style(painter, QRect(0, 0, canvas_size, canvas_size), monochrome.scaled(330))
    painter.end()

    cell_side = canvas_size / bounded_grid
    filled: list[tuple[int, int]] = []
    for y in range(bounded_grid):
        for x in range(bounded_grid):
            left = int(x * cell_side)
            top = int(y * cell_side)
            right = int((x + 1) * cell_side)
            bottom = int((y + 1) * cell_side)
            has_pixel = False
            for py in range(top, bottom):
                if has_pixel:
                    break
                for px in range(left, right):
                    # `QImage.pixel()` drops alpha for this image format; use pixelColor().
                    if image.pixelColor(px, py).alpha() > 0:
                        has_pixel = True
                        break
            if has_pixel:
                filled.append((x, y))

    color_hex = QColor(*style.color_rgba).name().upper()
    creation_mode = "pixel" if style.shape == OverlayShape.CUSTOM_GRID else "draw"
    return CreatorCrosshair(
        name=model_name.strip() or style.display_name,
        grid_size=bounded_grid,
        creation_mode=creation_mode,
        color_hex=color_hex,
        filled_cells=filled,
        style_id=style.style_id,
    )
