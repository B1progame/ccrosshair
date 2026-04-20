from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from ..config import OverlayStyle


class SettingKind(str, Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    COLOR = "color"


@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    kind: SettingKind
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None


@dataclass(frozen=True)
class CrosshairDefinition:
    style: OverlayStyle
    family: str
    description: str
    tags: tuple[str, ...]
    editable_settings: tuple[SettingSpec, ...]
    source_type: str = "builtin"
    source_path: str = ""
    is_favorite: bool = False

    @property
    def style_id(self) -> str:
        return self.style.style_id

    @property
    def display_name(self) -> str:
        return self.style.display_name

    def with_style(self, style: OverlayStyle) -> "CrosshairDefinition":
        return replace(self, style=style)

    def with_favorite(self, favorite: bool) -> "CrosshairDefinition":
        return replace(self, is_favorite=favorite)


class EditableField:
    COLOR = SettingSpec("color_rgba", "Color", SettingKind.COLOR)
    THICKNESS = SettingSpec("thickness", "Thickness", SettingKind.INT, 1, 14, 1)
    SIZE = SettingSpec("arm_length", "Size", SettingKind.INT, 1, 40, 1)
    GAP = SettingSpec("gap", "Gap", SettingKind.INT, 0, 40, 1)
    OPACITY = SettingSpec("opacity", "Opacity", SettingKind.INT, 10, 255, 5)
    CENTER_DOT = SettingSpec("center_dot", "Center Dot", SettingKind.BOOL)
    CENTER_DOT_SIZE = SettingSpec("center_dot_size", "Dot Size", SettingKind.INT, 1, 20, 1)
    CIRCLE_RADIUS = SettingSpec("circle_radius", "Circle Radius", SettingKind.INT, 2, 40, 1)
    CIRCLE_THICKNESS = SettingSpec("circle_thickness", "Circle Thickness", SettingKind.INT, 1, 14, 1)
    OUTLINE_ENABLED = SettingSpec("outline_enabled", "Outline", SettingKind.BOOL)
    OUTLINE_THICKNESS = SettingSpec("outline_thickness", "Outline Thickness", SettingKind.INT, 1, 10, 1)
    ROTATION = SettingSpec("rotation_degrees", "Rotation", SettingKind.FLOAT, -180, 180, 1)
    T_STYLE = SettingSpec("t_style", "T Style", SettingKind.BOOL)


def style_with_updates(style: OverlayStyle, updates: dict[str, Any]) -> OverlayStyle:
    payload: dict[str, Any] = {
        "style_id": style.style_id,
        "display_name": style.display_name,
        "shape": style.shape,
        "arm_length": style.arm_length,
        "gap": style.gap,
        "thickness": style.thickness,
        "color_rgba": style.color_rgba,
        "center_dot": style.center_dot,
        "center_dot_size": style.center_dot_size,
        "circle_radius": style.circle_radius,
        "circle_thickness": style.circle_thickness,
        "custom_grid_size": style.custom_grid_size,
        "custom_filled_cells": style.custom_filled_cells,
        "custom_cell_size": style.custom_cell_size,
        "t_style": style.t_style,
        "outline_enabled": style.outline_enabled,
        "outline_thickness": style.outline_thickness,
        "outline_rgba": style.outline_rgba,
        "rotation_degrees": style.rotation_degrees,
    }
    payload.update(updates)
    return OverlayStyle(**payload)
