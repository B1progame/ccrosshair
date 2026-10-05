from __future__ import annotations

from collections import OrderedDict

from ..config import OverlayShape, OverlayStyle
from .models import CrosshairDefinition, EditableField, SettingSpec
from .extended_catalog import load_original_expansion


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
        editable_settings=tuple((*editable, EditableField.OUTLINE_COLOR)) if any(item.key == "outline_enabled" for item in editable) and not any(item.key == "outline_rgba" for item in editable) else editable,
        source_type="builtin",
        aliases=(name.casefold().replace(" ", "-"), shape.value.replace("_", " ")),
        origin_game="Generic FPS",
        source_url="https://playvalorant.com/en-us/news/game-updates/valorant-patch-notes-5-04/",
        reuse_status="original pattern; not a copied game asset",
        approximate=False,
        catalog_version=1,
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
                "Pixel PvP",
                shape,
                "Original pixel-forward minimalist marker intended for PvP use.",
                ("pvp", "pixel", "original"),
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

    # Add geometry variants (not color clones) so the offline library covers
    # precision dots, open/T crosses, rings, brackets, chevrons and scope guides.
    signatures = {
        (p.style.shape, p.style.arm_length, p.style.gap, p.style.thickness,
         p.style.center_dot, p.style.center_dot_size, p.style.circle_radius,
         p.style.circle_thickness, p.style.t_style, p.style.outline_enabled)
        for p in presets
    }

    def add_geometry(style_id: str, name: str, family: str, shape: OverlayShape,
                     arm: int, gap: int, thickness: int, dot: bool = False,
                     dot_size: int = 2, radius: int = 8, ring: int = 1,
                     t_style: bool = False, outlined: bool = False,
                     tags: tuple[str, ...] = ()) -> None:
        sig = (shape, arm, gap, thickness, dot, dot_size, radius, ring, t_style, outlined)
        if style_id in catalog or sig in signatures:
            return
        signatures.add(sig)
        presets.append(_make(
            style_id, name, family, shape,
            f"Original {family.lower()} geometry preset with a distinct size and center layout.",
            tuple(dict.fromkeys((*tags, family.casefold().replace(" / ", " "), "original"))),
            _settings(EditableField.COLOR, EditableField.THICKNESS, EditableField.SIZE,
                      EditableField.GAP, EditableField.CENTER_DOT, EditableField.CENTER_DOT_SIZE,
                      EditableField.CIRCLE_RADIUS, EditableField.CIRCLE_THICKNESS,
                      EditableField.OPACITY, EditableField.OUTLINE_ENABLED, EditableField.OUTLINE_THICKNESS),
            arm_length=arm, gap=gap, thickness=thickness, center_dot=dot,
            center_dot_size=dot_size, circle_radius=radius, circle_thickness=ring,
            t_style=t_style, outline_enabled=outlined, outline_thickness=1,
        ))

    # Build stable size/gap/weight combinations, stopping at 100 total entries.
    candidates = []
    for arm, gap, weight in ((5, 1, 1), (6, 3, 1), (8, 5, 1), (11, 7, 1),
                             (14, 3, 1), (7, 9, 1), (12, 14, 2), (16, 6, 2),
                             (18, 10, 3), (4, 5, 1), (9, 0, 2), (15, 2, 1)):
        for t_style, dot in ((False, False), (False, True), (True, False)):
            candidates.append((f"cross_a{arm}_g{gap}_w{weight}_{'t' if t_style else 'dot' if dot else 'open'}",
                               f"Cross {arm} / Gap {gap} / {weight}px" + (" T" if t_style else " Dot" if dot else " Open"),
                               "Classic", OverlayShape.CLASSIC_CROSS, arm, gap, weight, dot, 2, 8, 1,
                               t_style, True, ("cross", "static", "precision")))
    for shape, family, tag in ((OverlayShape.DOT, "Precision Dot", "precision"),
                               (OverlayShape.RING, "Ring Sight", "ring"),
                               (OverlayShape.BRACKET, "Bracket", "bracket"),
                               (OverlayShape.CHEVRON, "Chevron", "chevron"),
                               (OverlayShape.SNIPER, "Sniper Guide", "sniper")):
        for arm, gap, weight in ((3, 0, 1), (5, 2, 1), (7, 4, 1), (9, 6, 2),
                                 (12, 8, 2), (15, 10, 3), (18, 4, 1), (22, 12, 2)):
            candidates.append((f"{tag}_{arm}_{gap}_{weight}", f"{family} {arm}-{gap}-{weight}", family,
                               shape, arm, gap, weight, shape == OverlayShape.DOT and arm > 5,
                               max(1, arm // 3), max(3, arm), weight, False, arm in (7, 12), (tag, "aim")))
    cross_variants, shape_variants = candidates[:36], candidates[36:]
    shape_families = [shape_variants[index:index + 8] for index in range(0, len(shape_variants), 8)]
    balanced_shapes = [family[round_index] for round_index in range(8) for family in shape_families]
    # Add a few distinct cross variants, then cycle every family evenly before
    # using the remaining cross variants. This preserves shape coverage at 100.
    candidates = [*cross_variants[:9], *balanced_shapes, *cross_variants[9:]]
    for data in candidates:
        if len(presets) >= 100:
            break
        add_geometry(*data)

    for item in presets[len(catalog):]:
        catalog[item.style_id] = item

    for item in load_original_expansion():
        if item.style_id in catalog:
            raise ValueError(f"Original expansion id collides with built-in style: {item.style_id}")
        catalog[item.style_id] = item

    return catalog


def default_style_id() -> str:
    return "classic_cross"
