from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from ..config import OverlayStyle
from ..creator.conversion import creator_to_overlay_style
from ..creator.io import load_creator_crosshair
from ..storage_paths import StoragePaths
from ..style_registry import load_style_pack
from .catalog import build_builtin_catalog, default_style_id
from .io import XHAIR_EXTENSION, XPACK_EXTENSION, load_xhair, load_xpack, save_xhair
from .models import CrosshairDefinition


class CrosshairLibrary:
    def __init__(self) -> None:
        self._definitions: "OrderedDict[str, CrosshairDefinition]" = OrderedDict()

    @property
    def definitions(self) -> "OrderedDict[str, CrosshairDefinition]":
        return self._definitions

    def load(self, storage_dir: Path) -> "OrderedDict[str, CrosshairDefinition]":
        layout = StoragePaths(storage_dir)
        layout.ensure()
        definitions = build_builtin_catalog()

        self._load_xhair_tree(layout.custom_dir, definitions, source_type="custom")
        self._load_xhair_tree(layout.imports_dir, definitions, source_type="imported_pack")
        self._load_chgrid_tree(layout.creator_dir, definitions, source_type="creator_grid")
        self._load_chgrid_tree(layout.imports_dir, definitions, source_type="creator_grid")

        # Backward compatibility for older flat storage layouts.
        self._load_loose_root_formats(storage_dir, definitions)

        self._definitions = definitions
        return self._definitions

    def ensure_style_id(self, style_id: str) -> str:
        return style_id if style_id in self._definitions else default_style_id()

    def style(self, style_id: str) -> OverlayStyle:
        return self._definitions[style_id].style

    def definition(self, style_id: str) -> CrosshairDefinition:
        return self._definitions[style_id]

    def definitions_for_ids(self, style_ids: list[str]) -> list[CrosshairDefinition]:
        return [self._definitions[style_id] for style_id in style_ids if style_id in self._definitions]

    def save_custom_definition(self, definition: CrosshairDefinition, storage_dir: Path) -> CrosshairDefinition:
        layout = StoragePaths(storage_dir)
        layout.ensure()
        clean = self._with_unique_id(definition, self._definitions)
        target = layout.custom_definition_path(clean.style_id)
        save_xhair(clean, target)
        persisted = CrosshairDefinition(
            style=clean.style,
            family=clean.family,
            description=clean.description,
            tags=clean.tags,
            editable_settings=clean.editable_settings,
            source_type="custom",
            source_path=str(target),
            is_favorite=clean.is_favorite,
        )
        self._definitions[persisted.style_id] = persisted
        return persisted

    def upsert_runtime_definition(self, definition: CrosshairDefinition) -> None:
        self._definitions[definition.style_id] = definition

    def set_favorite(self, style_id: str, value: bool) -> None:
        if style_id not in self._definitions:
            return
        self._definitions[style_id] = self._definitions[style_id].with_favorite(value)

    def _load_xhair_tree(
        self,
        root: Path,
        definitions: "OrderedDict[str, CrosshairDefinition]",
        source_type: str,
    ) -> None:
        if not root.exists():
            return
        for file in sorted(root.rglob(f"*{XHAIR_EXTENSION}")):
            try:
                definition = load_xhair(file)
                definition = self._with_unique_id(
                    CrosshairDefinition(
                        style=definition.style,
                        family=definition.family,
                        description=definition.description,
                        tags=definition.tags,
                        editable_settings=definition.editable_settings,
                        source_type=source_type,
                        source_path=str(file),
                        is_favorite=definition.is_favorite,
                    ),
                    definitions,
                )
                definitions[definition.style_id] = definition
            except Exception:
                continue

    def _load_chgrid_tree(
        self,
        root: Path,
        definitions: "OrderedDict[str, CrosshairDefinition]",
        source_type: str,
    ) -> None:
        if not root.exists():
            return
        for file in sorted(root.rglob("*.chgrid")):
            try:
                model = load_creator_crosshair(file)
                style = creator_to_overlay_style(model)
                definition = self._with_unique_id(
                    CrosshairDefinition(
                        style=style,
                        family="Creator Grid",
                        description="Imported from grid creator file.",
                        tags=("creator", "grid", "custom"),
                        editable_settings=(),
                        source_type=source_type,
                        source_path=str(file),
                    ),
                    definitions,
                )
                definitions[definition.style_id] = definition
            except Exception:
                continue

    def _load_loose_root_formats(
        self,
        storage_dir: Path,
        definitions: "OrderedDict[str, CrosshairDefinition]",
    ) -> None:
        for file in sorted(storage_dir.glob(f"*{XPACK_EXTENSION}")):
            try:
                for definition in load_xpack(file):
                    resolved = self._with_unique_id(definition, definitions)
                    definitions[resolved.style_id] = CrosshairDefinition(
                        style=resolved.style,
                        family=resolved.family,
                        description=resolved.description,
                        tags=resolved.tags,
                        editable_settings=resolved.editable_settings,
                        source_type="plugin_pack",
                        source_path=str(file),
                        is_favorite=resolved.is_favorite,
                    )
            except Exception:
                continue

        for file in sorted(storage_dir.glob("*.chpack")):
            try:
                style = load_style_pack(file)
                definition = CrosshairDefinition(
                    style=style,
                    family="Legacy Pack",
                    description="Imported from legacy .chpack format.",
                    tags=("legacy", "pack"),
                    editable_settings=build_builtin_catalog()[default_style_id()].editable_settings,
                    source_type="legacy_pack",
                    source_path=str(file),
                )
                definition = self._with_unique_id(definition, definitions)
                definitions[definition.style_id] = definition
            except Exception:
                continue

        for file in sorted(storage_dir.glob(f"*{XHAIR_EXTENSION}")):
            try:
                definition = load_xhair(file)
                definition = self._with_unique_id(
                    CrosshairDefinition(
                        style=definition.style,
                        family=definition.family,
                        description=definition.description,
                        tags=definition.tags,
                        editable_settings=definition.editable_settings,
                        source_type="custom",
                        source_path=str(file),
                        is_favorite=definition.is_favorite,
                    ),
                    definitions,
                )
                definitions[definition.style_id] = definition
            except Exception:
                continue

    def _with_unique_id(
        self,
        definition: CrosshairDefinition,
        pool: "OrderedDict[str, CrosshairDefinition]",
    ) -> CrosshairDefinition:
        base = definition.style_id.strip().lower().replace(" ", "_") or "custom_crosshair"
        candidate = base
        index = 2
        while candidate in pool:
            candidate = f"{base}_{index}"
            index += 1
        if candidate == definition.style_id:
            return definition
        style = OverlayStyle(
            style_id=candidate,
            display_name=definition.display_name,
            shape=definition.style.shape,
            arm_length=definition.style.arm_length,
            gap=definition.style.gap,
            thickness=definition.style.thickness,
            color_rgba=definition.style.color_rgba,
            center_dot=definition.style.center_dot,
            center_dot_size=definition.style.center_dot_size,
            circle_radius=definition.style.circle_radius,
            circle_thickness=definition.style.circle_thickness,
            custom_grid_size=definition.style.custom_grid_size,
            custom_filled_cells=definition.style.custom_filled_cells,
            custom_cell_size=definition.style.custom_cell_size,
            t_style=definition.style.t_style,
            outline_enabled=definition.style.outline_enabled,
            outline_thickness=definition.style.outline_thickness,
            outline_rgba=definition.style.outline_rgba,
            rotation_degrees=definition.style.rotation_degrees,
        )
        return CrosshairDefinition(
            style=style,
            family=definition.family,
            description=definition.description,
            tags=definition.tags,
            editable_settings=definition.editable_settings,
            source_type=definition.source_type,
            source_path=definition.source_path,
            is_favorite=definition.is_favorite,
        )
