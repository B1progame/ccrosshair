from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from .config import OverlayShape, OverlayStyle
from .crosshairs.catalog import build_builtin_catalog


def build_builtin_styles() -> "OrderedDict[str, OverlayStyle]":
    catalog = build_builtin_catalog()
    return OrderedDict((item.style_id, item.style) for item in catalog.values())


def default_style_id() -> str:
    return "classic_cross"


def overlay_style_to_dict(style: OverlayStyle) -> dict:
    return {
        "style_id": style.style_id,
        "display_name": style.display_name,
        "shape": style.shape.value,
        "arm_length": style.arm_length,
        "gap": style.gap,
        "thickness": style.thickness,
        "color_rgba": list(style.color_rgba),
        "center_dot": style.center_dot,
        "center_dot_size": style.center_dot_size,
        "circle_radius": style.circle_radius,
        "circle_thickness": style.circle_thickness,
        "custom_grid_size": style.custom_grid_size,
        "custom_filled_cells": [[x, y] for x, y in style.custom_filled_cells],
        "custom_cell_size": style.custom_cell_size,
        "t_style": style.t_style,
        "outline_enabled": style.outline_enabled,
        "outline_thickness": style.outline_thickness,
        "outline_rgba": list(style.outline_rgba),
        "rotation_degrees": style.rotation_degrees,
    }


def overlay_style_from_dict(payload: dict) -> OverlayStyle:
    shape_value = payload.get("shape", OverlayShape.CLASSIC_CROSS.value)
    try:
        shape = OverlayShape(shape_value)
    except ValueError:
        shape = OverlayShape.CLASSIC_CROSS

    color_raw = payload.get("color_rgba", [255, 255, 255, 255])
    if not isinstance(color_raw, list) or len(color_raw) != 4:
        color_raw = [255, 255, 255, 255]
    color = tuple(int(max(0, min(255, value))) for value in color_raw)

    outline_raw = payload.get("outline_rgba", [0, 0, 0, 220])
    if not isinstance(outline_raw, list) or len(outline_raw) != 4:
        outline_raw = [0, 0, 0, 220]
    outline = tuple(int(max(0, min(255, value))) for value in outline_raw)

    custom_cells_raw = payload.get("custom_filled_cells", [])
    custom_cells: list[tuple[int, int]] = []
    if isinstance(custom_cells_raw, list):
        for cell in custom_cells_raw:
            if isinstance(cell, list) and len(cell) == 2:
                custom_cells.append((int(cell[0]), int(cell[1])))

    return OverlayStyle(
        style_id=str(payload.get("style_id", "imported_crosshair")).strip() or "imported_crosshair",
        display_name=str(payload.get("display_name", "Imported Crosshair")).strip() or "Imported Crosshair",
        shape=shape,
        arm_length=int(payload.get("arm_length", 10)),
        gap=int(payload.get("gap", 4)),
        thickness=int(payload.get("thickness", 1)),
        color_rgba=color,  # type: ignore[arg-type]
        center_dot=bool(payload.get("center_dot", True)),
        center_dot_size=int(payload.get("center_dot_size", 2)),
        circle_radius=int(payload.get("circle_radius", 8)),
        circle_thickness=int(payload.get("circle_thickness", 1)),
        custom_grid_size=max(8, min(64, int(payload.get("custom_grid_size", 32)))),
        custom_filled_cells=tuple(custom_cells),
        custom_cell_size=max(1, min(12, int(payload.get("custom_cell_size", 1)))),
        t_style=bool(payload.get("t_style", False)),
        outline_enabled=bool(payload.get("outline_enabled", False)),
        outline_thickness=max(1, int(payload.get("outline_thickness", 1))),
        outline_rgba=outline,  # type: ignore[arg-type]
        rotation_degrees=float(payload.get("rotation_degrees", 0.0)),
    )


def save_style_pack(style: OverlayStyle, destination: Path) -> None:
    payload = {
        "format": "crosshair-overlay-pack-v1",
        "style": overlay_style_to_dict(style),
    }
    destination.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_style_pack(source: Path) -> OverlayStyle:
    payload = json.loads(source.read_text(encoding="utf-8"))
    style_payload = payload.get("style", {})
    if not isinstance(style_payload, dict):
        raise ValueError("Invalid crosshair pack format.")
    return overlay_style_from_dict(style_payload)
