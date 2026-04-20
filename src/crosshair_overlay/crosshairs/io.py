from __future__ import annotations

import json
from pathlib import Path

from ..config import OverlayShape, OverlayStyle
from .models import CrosshairDefinition, EditableField, SettingKind, SettingSpec

XHAIR_FORMAT = "crosshair-overlay-xhair-v1"
XPACK_FORMAT = "crosshair-overlay-xpack-v1"
XHAIR_EXTENSION = ".xhair"
XPACK_EXTENSION = ".xpack"


def setting_to_dict(item: SettingSpec) -> dict:
    return {
        "key": item.key,
        "label": item.label,
        "kind": item.kind.value,
        "min": item.minimum,
        "max": item.maximum,
        "step": item.step,
    }


def setting_from_dict(payload: dict) -> SettingSpec:
    kind = payload.get("kind", SettingKind.INT.value)
    try:
        parsed_kind = SettingKind(kind)
    except ValueError:
        parsed_kind = SettingKind.INT
    return SettingSpec(
        key=str(payload.get("key", "")),
        label=str(payload.get("label", "")),
        kind=parsed_kind,
        minimum=payload.get("min"),
        maximum=payload.get("max"),
        step=payload.get("step"),
    )


def style_to_dict(style: OverlayStyle) -> dict:
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


def style_from_dict(payload: dict) -> OverlayStyle:
    try:
        shape = OverlayShape(payload.get("shape", OverlayShape.CLASSIC_CROSS.value))
    except ValueError:
        shape = OverlayShape.CLASSIC_CROSS

    color = payload.get("color_rgba", [255, 255, 255, 255])
    if not isinstance(color, list) or len(color) != 4:
        color = [255, 255, 255, 255]

    outline_color = payload.get("outline_rgba", [0, 0, 0, 220])
    if not isinstance(outline_color, list) or len(outline_color) != 4:
        outline_color = [0, 0, 0, 220]

    cells_raw = payload.get("custom_filled_cells", [])
    cells: list[tuple[int, int]] = []
    if isinstance(cells_raw, list):
        for cell in cells_raw:
            if isinstance(cell, list) and len(cell) == 2:
                cells.append((int(cell[0]), int(cell[1])))

    return OverlayStyle(
        style_id=str(payload.get("style_id", "imported_crosshair")).strip() or "imported_crosshair",
        display_name=str(payload.get("display_name", "Imported Crosshair")).strip() or "Imported Crosshair",
        shape=shape,
        arm_length=int(payload.get("arm_length", 10)),
        gap=max(0, int(payload.get("gap", 4))),
        thickness=max(1, int(payload.get("thickness", 1))),
        color_rgba=tuple(max(0, min(255, int(v))) for v in color),  # type: ignore[arg-type]
        center_dot=bool(payload.get("center_dot", True)),
        center_dot_size=max(1, int(payload.get("center_dot_size", 2))),
        circle_radius=max(1, int(payload.get("circle_radius", 8))),
        circle_thickness=max(1, int(payload.get("circle_thickness", 1))),
        custom_grid_size=max(8, min(64, int(payload.get("custom_grid_size", 32)))),
        custom_filled_cells=tuple(cells),
        custom_cell_size=max(1, min(12, int(payload.get("custom_cell_size", 1)))),
        t_style=bool(payload.get("t_style", False)),
        outline_enabled=bool(payload.get("outline_enabled", False)),
        outline_thickness=max(1, int(payload.get("outline_thickness", 1))),
        outline_rgba=tuple(max(0, min(255, int(v))) for v in outline_color),  # type: ignore[arg-type]
        rotation_degrees=float(payload.get("rotation_degrees", 0.0)),
    )


def definition_to_dict(item: CrosshairDefinition) -> dict:
    return {
        "format": XHAIR_FORMAT,
        "style": style_to_dict(item.style),
        "family": item.family,
        "description": item.description,
        "tags": list(item.tags),
        "editable_settings": [setting_to_dict(x) for x in item.editable_settings],
        "source_type": item.source_type,
        "source_path": item.source_path,
        "is_favorite": item.is_favorite,
    }


def definition_from_dict(payload: dict) -> CrosshairDefinition:
    if "style" not in payload:
        raise ValueError("Missing style payload")
    editable_raw = payload.get("editable_settings", [])
    editable: list[SettingSpec] = []
    if isinstance(editable_raw, list):
        for item in editable_raw:
            if isinstance(item, dict):
                editable.append(setting_from_dict(item))
    if not editable:
        editable = [
            EditableField.COLOR,
            EditableField.THICKNESS,
            EditableField.SIZE,
            EditableField.GAP,
            EditableField.OPACITY,
        ]

    return CrosshairDefinition(
        style=style_from_dict(payload["style"]),
        family=str(payload.get("family", "Custom")),
        description=str(payload.get("description", "Imported crosshair")),
        tags=tuple(str(x) for x in payload.get("tags", [])),
        editable_settings=tuple(editable),
        source_type=str(payload.get("source_type", "plugin")),
        source_path=str(payload.get("source_path", "")),
        is_favorite=bool(payload.get("is_favorite", False)),
    )


def save_xhair(definition: CrosshairDefinition, destination: Path) -> None:
    destination.write_text(json.dumps(definition_to_dict(definition), ensure_ascii=True, indent=2), encoding="utf-8")


def load_xhair(source: Path) -> CrosshairDefinition:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") != XHAIR_FORMAT:
        raise ValueError("Unsupported .xhair format version")
    item = definition_from_dict(payload)
    return item.with_style(item.style)


def save_xpack(definitions: list[CrosshairDefinition], destination: Path, metadata: dict | None = None) -> None:
    payload = {
        "format": XPACK_FORMAT,
        "crosshairs": [definition_to_dict(item) for item in definitions],
    }
    if metadata:
        payload["metadata"] = metadata
    destination.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def load_xpack(source: Path) -> list[CrosshairDefinition]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") != XPACK_FORMAT:
        raise ValueError("Unsupported .xpack format version")
    items = payload.get("crosshairs", [])
    if not isinstance(items, list):
        raise ValueError("Invalid .xpack crosshairs payload")
    loaded: list[CrosshairDefinition] = []
    for item in items:
        if isinstance(item, dict):
            loaded.append(definition_from_dict(item))
    return loaded
