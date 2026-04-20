from __future__ import annotations

from collections import OrderedDict

from ..config import OverlayShape, OverlayStyle
from .models import CrosshairDefinition, EditableField, SettingSpec


def _settings(*items: SettingSpec) -> tuple[SettingSpec, ...]:
    return items


def _make(
    style_id: str,
    name: str,
    family: str,
    shape: OverlayShape,
    description: str,
    tags: tuple[str, ...],
    editable: tuple[SettingSpec, ...],
    **kwargs,
) -> CrosshairDefinition:
    style = OverlayStyle(
        style_id=style_id,
        display_name=name,
        shape=shape,
        **kwargs,
    )
    return CrosshairDefinition(
        style=style,
        family=family,
        description=description,
        tags=tags,
        editable_settings=editable,
        source_type="builtin",
    )


def build_builtin_catalog() -> "OrderedDict[str, CrosshairDefinition]":
    catalog: "OrderedDict[str, CrosshairDefinition]" = OrderedDict()

    presets = [
        _make(
            "classic_cross",
            "Classic Cross",
            "Classic",
            OverlayShape.CLASSIC_CROSS,
            "Balanced four-line cross with center dot.",
            ("fps", "classic", "balanced"),
            _settings(
                EditableField.COLOR,
                EditableField.THICKNESS,
                EditableField.SIZE,
                EditableField.GAP,
                EditableField.CENTER_DOT,
                EditableField.CENTER_DOT_SIZE,
                EditableField.OPACITY,
                EditableField.OUTLINE_ENABLED,
                EditableField.OUTLINE_THICKNESS,
                EditableField.T_STYLE,
            ),
            arm_length=10,
            gap=4,
            thickness=1,
            center_dot=True,
            center_dot_size=2,
            outline_enabled=True,
            outline_thickness=1,
        ),
        _make(
            "dot_micro",
            "Dot Micro",
            "Dot",
            OverlayShape.DOT,
            "Very small precision dot.",
            ("dot", "minimal", "precision"),
            _settings(EditableField.COLOR, EditableField.CENTER_DOT_SIZE, EditableField.OPACITY, EditableField.OUTLINE_ENABLED),
            center_dot_size=2,
            center_dot=True,
            outline_enabled=True,
            outline_thickness=1,
        ),
        _make(
            "dot_pro",
            "Dot Pro",
            "Dot",
            OverlayShape.DOT,
            "Dot with stronger visibility.",
            ("dot", "esports"),
            _settings(EditableField.COLOR, EditableField.CENTER_DOT_SIZE, EditableField.OPACITY, EditableField.OUTLINE_ENABLED),
            center_dot_size=4,
            center_dot=True,
            outline_enabled=True,
            outline_thickness=1,
        ),
    ]

    circle_base = [
        ("circle_cross_compact", "Circle Cross Compact", 7, 8, 1, 8),
        ("circle_cross_balanced", "Circle Cross Balanced", 9, 10, 1, 9),
        ("circle_cross_wide", "Circle Cross Wide", 11, 12, 1, 10),
        ("ring_dot_precision", "Ring Dot Precision", 0, 9, 2, 0),
        ("ring_tactical", "Ring Tactical", 0, 12, 2, 0),
    ]
    for style_id, name, arm, radius, thickness, gap in circle_base:
        shape = OverlayShape.CIRCLE_CROSS if arm > 0 else OverlayShape.RING
        presets.append(
            _make(
                style_id,
                name,
                "Ring / Circle",
                shape,
                "Circle-driven reticle for focus-heavy aiming.",
                ("ring", "circle", "tracking"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.CIRCLE_RADIUS,
                    EditableField.CIRCLE_THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                circle_radius=radius,
                circle_thickness=thickness,
                center_dot=True,
                center_dot_size=2,
                outline_enabled=False,
            )
        )

    classic_variants = [
        ("classic_t_style", "Classic T-Style", 10, 4, 2, True),
        ("classic_long_gap", "Classic Long Gap", 12, 12, 1, False),
        ("classic_short_gap", "Classic Tight Gap", 9, 2, 1, False),
        ("classic_heavy", "Classic Heavy", 9, 4, 3, False),
        ("classic_rotated", "Classic Rotated", 9, 4, 1, False),
    ]
    for style_id, name, arm, gap, thickness, t_style in classic_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Classic",
                OverlayShape.CLASSIC_CROSS,
                "Cross family inspired by FPS static reticles.",
                ("cross", "fps", "static"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                    EditableField.T_STYLE,
                    EditableField.ROTATION,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                center_dot=True,
                center_dot_size=2,
                t_style=t_style,
                rotation_degrees=45.0 if style_id == "classic_rotated" else 0.0,
                outline_enabled=thickness <= 2,
                outline_thickness=1,
            )
        )

    bracket_variants = [
        ("bracket_small", "Bracket Small", 7, 8, 1),
        ("bracket_balanced", "Bracket Balanced", 10, 8, 1),
        ("bracket_open", "Bracket Open", 11, 14, 1),
        ("bracket_heavy", "Bracket Heavy", 10, 9, 3),
        ("selector_corner", "Selector Corner", 12, 16, 2),
    ]
    for style_id, name, arm, gap, thickness in bracket_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Bracket",
                OverlayShape.BRACKET,
                "Corner-style bracket reticle for low center clutter.",
                ("bracket", "corner", "selector"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                    EditableField.ROTATION,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                center_dot=False,
                outline_enabled=thickness <= 2,
                outline_thickness=1,
            )
        )

    diamond_variants = [
        ("diamond_micro", "Diamond Micro", 6, 5, 1),
        ("diamond_balanced", "Diamond Balanced", 8, 6, 1),
        ("diamond_fine", "Diamond Fine", 10, 7, 1),
        ("diamond_heavy", "Diamond Heavy", 10, 8, 2),
    ]
    for style_id, name, arm, gap, thickness in diamond_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Diamond",
                OverlayShape.DIAMOND,
                "Diamond marker style used for center clarity.",
                ("diamond", "marker"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                center_dot=style_id != "diamond_micro",
                center_dot_size=2,
                outline_enabled=True,
                outline_thickness=1,
            )
        )

    square_variants = [
        ("square_hollow", "Square Hollow", 10, 7, 1, False),
        ("square_dot", "Square Dot", 10, 7, 1, True),
        ("square_wide", "Square Wide", 12, 10, 1, False),
        ("square_heavy", "Square Heavy", 11, 8, 2, True),
    ]
    for style_id, name, arm, gap, thickness, dot in square_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Square",
                OverlayShape.SQUARE,
                "Box-like reticle inspired by tactical shooter selectors.",
                ("square", "box", "selector"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                center_dot=dot,
                center_dot_size=2,
                outline_enabled=True,
                outline_thickness=1,
            )
        )

    tactical_variants = [
        ("sniper_scope_min", "Sniper Scope Min", 0, 0, 1, 18),
        ("sniper_scope_dot", "Sniper Scope Dot", 0, 0, 1, 16),
        ("target_ring_light", "Target Ring Light", 5, 6, 1, 14),
        ("target_ring_focus", "Target Ring Focus", 7, 8, 2, 15),
        ("focus_reticle", "Focus Reticle", 6, 10, 1, 12),
        ("focus_reticle_heavy", "Focus Reticle Heavy", 8, 11, 2, 12),
    ]
    for style_id, name, arm, gap, thickness, radius in tactical_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Target / Scope",
                OverlayShape.CIRCLE_CROSS if arm > 0 else OverlayShape.RING,
                "Targeting reticles inspired by scope and ring sights.",
                ("target", "scope", "ring"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CIRCLE_RADIUS,
                    EditableField.CIRCLE_THICKNESS,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                    EditableField.OUTLINE_THICKNESS,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                circle_radius=radius,
                circle_thickness=1 if thickness == 1 else 2,
                center_dot=style_id != "sniper_scope_min",
                center_dot_size=2,
                outline_enabled=False,
            )
        )

    pvp_variants = [
        ("pvp_pixel_plus", "PvP Pixel Plus", OverlayShape.CLASSIC_CROSS, 7, 2, 1),
        ("pvp_pixel_dot", "PvP Pixel Dot", OverlayShape.DOT, 0, 0, 1),
        ("pvp_square_dot", "PvP Square Dot", OverlayShape.SQUARE, 9, 5, 1),
        ("pvp_bracket", "PvP Bracket", OverlayShape.BRACKET, 9, 10, 1),
        ("pvp_ring", "PvP Ring", OverlayShape.RING, 0, 0, 1),
    ]
    for style_id, name, shape, arm, gap, thickness in pvp_variants:
        presets.append(
            _make(
                style_id,
                name,
                "Minecraft / PvP",
                shape,
                "Pixel-forward minimalist style from PvP pack families.",
                ("minecraft", "pvp", "pixel"),
                _settings(
                    EditableField.COLOR,
                    EditableField.THICKNESS,
                    EditableField.SIZE,
                    EditableField.GAP,
                    EditableField.CENTER_DOT,
                    EditableField.CENTER_DOT_SIZE,
                    EditableField.OPACITY,
                    EditableField.OUTLINE_ENABLED,
                ),
                arm_length=arm,
                gap=gap,
                thickness=thickness,
                circle_radius=8,
                circle_thickness=1,
                center_dot=shape != OverlayShape.DOT,
                center_dot_size=2 if shape != OverlayShape.DOT else 4,
                outline_enabled=True,
                outline_thickness=1,
            )
        )

    for item in presets:
        catalog[item.style_id] = item

    return catalog


def default_style_id() -> str:
    return "classic_cross"
