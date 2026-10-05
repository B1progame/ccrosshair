from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class OverlayShape(str, Enum):
    CLASSIC_CROSS = "classic_cross"
    DOT = "dot"
    CIRCLE_CROSS = "circle_cross"
    CUSTOM_GRID = "custom_grid"
    BRACKET = "bracket"
    DIAMOND = "diamond"
    RING = "ring"
    SQUARE = "square"
    CHEVRON = "chevron"
    SNIPER = "sniper"


@dataclass(frozen=True)
class OverlayStyle:
    """Overlay render style model."""

    style_id: str
    display_name: str
    shape: OverlayShape
    arm_length: int = 10
    gap: int = 4
    thickness: int = 1
    color_rgba: Tuple[int, int, int, int] = (255, 255, 255, 255)
    center_dot: bool = True
    center_dot_size: int = 2
    circle_radius: int = 8
    circle_thickness: int = 1
    custom_grid_size: int = 32
    custom_filled_cells: Tuple[Tuple[int, int], ...] = ()
    custom_cell_size: int = 1
    t_style: bool = False
    outline_enabled: bool = False
    outline_thickness: int = 1
    outline_rgba: Tuple[int, int, int, int] = (0, 0, 0, 220)
    rotation_degrees: float = 0.0

    @property
    def canvas_size(self) -> int:
        """
        Compact square canvas that fully contains the overlay shape.
        The returned size is always odd so the crosshair center stays on
        the same pixel while scaling and does not visually "jump around".
        """
        line_stroke = self.thickness + (self.outline_thickness * 2 if self.outline_enabled else 0)
        circle_stroke = self.circle_thickness + (self.outline_thickness * 2 if self.outline_enabled else 0)
        dot_span = self.center_dot_size + (self.outline_thickness * 2 if self.outline_enabled else 0)

        half_extents = [dot_span / 2.0]

        if self.shape in {OverlayShape.CLASSIC_CROSS, OverlayShape.CIRCLE_CROSS}:
            cross_half = self.arm_length + (self.gap / 2.0) + (line_stroke / 2.0)
            half_extents.append(cross_half)

        if self.shape in {OverlayShape.CIRCLE_CROSS, OverlayShape.RING}:
            ring_half = self.circle_radius + (circle_stroke / 2.0)
            half_extents.append(ring_half)

        if self.shape == OverlayShape.BRACKET:
            bracket_half = self.arm_length + (self.gap / 2.0) + (line_stroke / 2.0)
            half_extents.append(bracket_half)

        if self.shape == OverlayShape.SQUARE:
            square_half = max(2.0, self.gap / 2.0 + self.arm_length / 2.0) + (line_stroke / 2.0)
            half_extents.append(square_half)

        if self.shape == OverlayShape.DIAMOND:
            diamond_half = max(2.0, self.arm_length / 2.0 + self.gap / 3.0) + (line_stroke / 2.0)
            half_extents.append(diamond_half)

        if self.shape == OverlayShape.CHEVRON:
            half_extents.append(self.arm_length + line_stroke / 2.0)

        if self.shape == OverlayShape.SNIPER:
            half_extents.append(self.arm_length + line_stroke / 2.0)

        if self.shape == OverlayShape.CUSTOM_GRID:
            grid_span = self.custom_grid_size * max(1, self.custom_cell_size)
            half_extents.append(grid_span / 2.0)

        max_half_extent = max(half_extents)
        if abs(self.rotation_degrees) > 0.01:
            max_half_extent *= math.sqrt(2)

        size = int(math.ceil((max_half_extent * 2.0) + 4.0))
        if size % 2 == 0:
            size += 1
        return max(9, size)

    def scaled(self, scale_percent: int) -> "OverlayStyle":
        factor = max(20, min(400, scale_percent)) / 100.0

        def scaled_int(value: int, minimum: int = 1) -> int:
            return max(minimum, int(round(value * factor)))

        return OverlayStyle(
            style_id=self.style_id,
            display_name=self.display_name,
            shape=self.shape,
            arm_length=scaled_int(self.arm_length),
            gap=scaled_int(self.gap, minimum=0),
            thickness=scaled_int(self.thickness),
            color_rgba=self.color_rgba,
            center_dot=self.center_dot,
            center_dot_size=scaled_int(self.center_dot_size),
            circle_radius=scaled_int(self.circle_radius),
            circle_thickness=scaled_int(self.circle_thickness),
            custom_grid_size=self.custom_grid_size,
            custom_filled_cells=self.custom_filled_cells,
            custom_cell_size=scaled_int(self.custom_cell_size),
            t_style=self.t_style,
            outline_enabled=self.outline_enabled,
            outline_thickness=scaled_int(self.outline_thickness),
            outline_rgba=self.outline_rgba,
            rotation_degrees=self.rotation_degrees,
        )
