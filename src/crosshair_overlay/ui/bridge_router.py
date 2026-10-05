from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog

from ..app_settings import BetaZoomSettings
from ..creator.models import CreatorCrosshair
from ..crosshairs.models import CrosshairDefinition, SettingKind, style_with_updates


class BridgeCommandRouter:
    """Validate and route the finite set of commands exposed to bundled React UI."""

    FIELDS = {
        "ready": set(), "navigate": {"page"}, "queryCatalog": {"query", "filter", "page", "pageSize"}, "quit": set(),
        "selectStyle": {"styleId"}, "activateStyle": {"styleId"}, "toggleFavorite": {"styleId"},
        "openDetail": {"styleId"}, "updateStyle": {"styleId", "updates"}, "saveVariant": {"styleId"},
        "sendToCreator": {"styleId"}, "setOverlay": {"enabled"}, "setTheme": {"theme"},
        "setAccent": {"color"}, "setSelectedSize": {"value"}, "setGlobalSize": {"value"},
        "setSidebarCollapsed": {"collapsed"},
        "setStartup": {"preference", "enabled"}, "setFullscreenAuto": {"enabled"},
        "setGameAutoSwitch": {"enabled"}, "setBetaVisible": {"enabled"}, "importPack": set(), "exportStyle": {"styleId"},
        "exportCurrent": set(), "exportSelection": {"styleIds"}, "creatorSave": {"model", "activate"},
        "creatorExport": {"model"}, "setGameProfile": {"gameId", "styleId", "enabled"},
        "importGame": set(), "rescanGames": set(), "setZoom": {"settings": {"sidebarEnabled", "liveEnabled", "zoomEnabled", "hotkeySequence", "displayMode", "targetMonitorId", "positionXPercent", "positionYPercent", "zoomPercent", "animationEnabled", "animationDurationMs"}},
        "chooseStorage": set(), "checkUpdates": set(), "resetSettings": set(),
    }
    PAGES = {"home", "library", "my_crosshairs", "creator", "games", "zoom", "export", "settings", "about", "detail"}
    STYLE_FIELDS = {
        "arm_length": ("armLength", int), "gap": ("gap", int), "thickness": ("thickness", int),
        "center_dot": ("dot", bool), "center_dot_size": ("centerDotSize", int),
        "circle_radius": ("circleRadius", int), "circle_thickness": ("circleThickness", int),
        "outline_enabled": ("outlineEnabled", bool), "outline_thickness": ("outlineThickness", int),
        "rotation_degrees": ("rotationDegrees", float), "t_style": ("tStyle", bool),
    }

    def __init__(self, window) -> None:
        self.window = window

    def dispatch(self, command: str, payload: dict) -> object:
        if command not in self.FIELDS:
            raise ValueError("Unsupported command")
        expected = self.FIELDS[command]
        if command == "setZoom":
            settings = payload.get("settings")
            if set(payload) != {"settings"} or not isinstance(settings, dict) or set(settings) != expected["settings"]:
                raise ValueError("Invalid zoom settings")
        elif set(payload) != expected:
            raise ValueError("Invalid command payload")

        w = self.window
        if command == "ready": return w._publish_web_state()
        if command == "navigate":
            page = payload["page"]
            if page not in self.PAGES: raise ValueError("Unsupported page")
            w._web_page = page
            w._current_page_id = "zoom" if page == "beta" else page
            return {"accepted": True, "page": page}
        if command == "queryCatalog": return self._query_catalog(payload)
        if command == "quit": w.quit_requested.emit(); return {"accepted": True}
        if command in {"selectStyle", "activateStyle", "toggleFavorite", "openDetail", "saveVariant", "sendToCreator"}:
            style_id = self._style_id(payload.get("styleId"))
            w._web_selected_id = style_id
            if command == "selectStyle": pass
            elif command == "activateStyle": w.style_selected.emit(style_id)
            elif command == "toggleFavorite": w.style_favorite_toggled.emit(style_id)
            elif command == "openDetail":
                w._web_page = "detail"
                w._current_page_id = "detail"
            elif command == "saveVariant":
                w.style_variant_save_requested.emit(w._definitions[style_id])
            else: w.send_to_editor_requested.emit(style_id)
            w._publish_web_event()
            return {"accepted": True, "selectedId": style_id}
        if command == "updateStyle": return self._update_style(payload)
        if command == "setOverlay":
            enabled = payload["enabled"]
            if not isinstance(enabled, bool): raise ValueError("enabled must be a boolean")
            (w.enable_overlay_requested if enabled else w.disable_overlay_requested).emit()
            return {"accepted": True}
        if command == "setTheme":
            theme = payload["theme"]
            if theme not in {"light", "dark", "system"}: raise ValueError("Unsupported theme")
            w.theme_mode_changed.emit(theme); return {"accepted": True}
        if command == "setAccent":
            color = payload["color"]
            if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color): raise ValueError("Accent must be a six-digit hex color")
            w.accent_color_changed.emit(color.upper()); return {"accepted": True}
        if command in {"setSelectedSize", "setGlobalSize"}:
            value = payload["value"]
            if type(value) is not int or not 50 <= value <= 200: raise ValueError("Size must be between 50 and 200")
            (w.selected_size_changed if command == "setSelectedSize" else w.global_size_changed).emit(value)
            return {"accepted": True}
        if command == "setSidebarCollapsed":
            collapsed = payload["collapsed"]
            if not isinstance(collapsed, bool): raise ValueError("collapsed must be a boolean")
            w._sidebar_collapsed = collapsed
            w.sidebar_collapsed_changed.emit(collapsed)
            w._publish_web_event()
            return {"accepted": True, "collapsed": collapsed}
        if command == "setStartup":
            preference, enabled = payload["preference"], payload["enabled"]
            if preference not in {"updates", "tray"} or not isinstance(enabled, bool): raise ValueError("Invalid startup preference")
            (w.auto_update_on_startup_changed if preference == "updates" else w.run_on_startup_tray_changed).emit(enabled)
            return {"accepted": True}
        if command in {"setFullscreenAuto", "setGameAutoSwitch"}:
            enabled = payload["enabled"]
            if not isinstance(enabled, bool): raise ValueError("enabled must be a boolean")
            (w.fullscreen_auto_toggled if command == "setFullscreenAuto" else w.game_auto_switch_toggled).emit(enabled)
            return {"accepted": True}
        if command == "setBetaVisible":
            enabled = payload["enabled"]
            if not isinstance(enabled, bool): raise ValueError("enabled must be a boolean")
            w.beta_features_changed.emit(enabled)
            return {"accepted": True}
        if command == "importPack":
            path, _ = QFileDialog.getOpenFileName(w, "Import Crosshair Pack", "", "Crosshair packs (*.xpack *.xhair *.chgrid);;All files (*.*)")
            if path: w.import_pack_requested.emit(path)
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command in {"exportStyle", "exportCurrent"}:
            style_id = self._style_id(payload["styleId"]) if command == "exportStyle" else w._active_style_id
            path, _ = QFileDialog.getSaveFileName(w, "Export Crosshair", f"{style_id}.xhair", "Crosshair (*.xhair)")
            if path: w.style_export_requested.emit(style_id, self._with_suffix(path, ".xhair"))
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "exportSelection":
            ids = payload["styleIds"]
            if not isinstance(ids, list) or len(ids) > 500 or any(not isinstance(x, str) or x not in w._definitions for x in ids): raise ValueError("Invalid export selection")
            path, _ = QFileDialog.getSaveFileName(w, "Export Selected Crosshairs", "crosshairs.xpack", "Crosshair pack (*.xpack)")
            if path: w.export_selection_requested.emit(ids, self._with_suffix(path, ".xpack"))
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command in {"creatorSave", "creatorExport"}:
            model = self._creator_model(payload["model"])
            if command == "creatorSave":
                if not isinstance(payload["activate"], bool): raise ValueError("activate must be a boolean")
                w.creator_save_requested.emit(model, payload["activate"])
                return {"accepted": True}
            path, _ = QFileDialog.getSaveFileName(w, "Export Creator Crosshair", f"{model.name or 'crosshair'}.chgrid", "Creator crosshair (*.chgrid)")
            if path: w.creator_export_requested.emit(model, self._with_suffix(path, ".chgrid"))
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "setGameProfile":
            game_id, style_id, enabled = payload["gameId"], payload["styleId"], payload["enabled"]
            if not isinstance(game_id, str) or not game_id or len(game_id) > 256 or (style_id and style_id not in w._definitions) or not isinstance(enabled, bool): raise ValueError("Invalid game profile")
            w.game_profile_updated.emit(game_id, style_id, enabled); return {"accepted": True}
        if command == "importGame":
            path, _ = QFileDialog.getOpenFileName(w, "Add Game Executable", "", "Applications (*.exe)")
            if path: w.import_game_requested.emit(path)
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "rescanGames": w.rescan_games_requested.emit(); return {"accepted": True}
        if command == "setZoom":
            w.beta_zoom_settings_changed.emit(self._zoom_settings(payload["settings"]))
            return {"accepted": True}
        if command == "chooseStorage":
            path = QFileDialog.getExistingDirectory(w, "Crosshair Storage Folder", w._storage_path)
            if path: w.storage_path_changed.emit(path)
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "checkUpdates": w.check_updates_requested.emit(); return {"accepted": True}
        if command == "resetSettings": w.reset_requested.emit(); return {"accepted": True}
        raise ValueError("Unsupported command")

    def _update_style(self, payload: dict) -> object:
        w = self.window
        style_id = self._style_id(payload["styleId"])
        changes = payload["updates"]
        if not isinstance(changes, dict) or not changes or len(changes) > 12:
            raise ValueError("Invalid style changes")
        definition = w._definitions[style_id]
        specs = {item.key: item for item in definition.editable_settings}
        updates = {}
        for key, value in changes.items():
            if key == "color":
                if "color_rgba" not in specs or not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value): raise ValueError("Color is not editable for this style")
                color = QColor(value)
                alpha = definition.style.color_rgba[3]
                updates["color_rgba"] = (color.red(), color.green(), color.blue(), alpha)
                continue
            if key == "opacity":
                spec = specs.get("opacity")
                if spec is None or type(value) is not int or spec.minimum is not None and value < spec.minimum or spec.maximum is not None and value > spec.maximum:
                    raise ValueError("Opacity is outside its allowed range")
                updates["color_rgba"] = (*definition.style.color_rgba[:3], value)
                continue
            if key not in self.STYLE_FIELDS:
                raise ValueError(f"Unsupported style field: {key}")
            native_key, cast = self.STYLE_FIELDS[key]
            spec = specs.get(native_key)
            if spec is None or (cast is bool and not isinstance(value, bool)) or (cast is not bool and (isinstance(value, bool) or not isinstance(value, (int, float)))):
                raise ValueError(f"{key} is not editable for this style")
            parsed = cast(value)
            if spec.minimum is not None and parsed < spec.minimum or spec.maximum is not None and parsed > spec.maximum:
                raise ValueError(f"{key} is outside its allowed range")
            updates[native_key] = parsed
        updated = definition.with_style(style_with_updates(definition.style, updates))
        w.style_live_updated.emit(updated)
        w._publish_web_event()
        return {"accepted": True, "styleId": style_id}

    def _style_id(self, value: object) -> str:
        if not isinstance(value, str) or value not in self.window._definitions:
            raise ValueError("Unknown crosshair style")
        return value

    def _query_catalog(self, payload: dict) -> dict:
        query, category, page, page_size = payload["query"], payload["filter"], payload["page"], payload["pageSize"]
        if not isinstance(query, str) or len(query) > 256 or category not in {"all", "my", "favorites", "creator", "imports", "custom"}:
            raise ValueError("Invalid catalog query")
        if type(page) is not int or not 0 <= page <= 10000 or type(page_size) is not int or not 1 <= page_size <= 48:
            raise ValueError("Catalog page is out of range")
        needle = query.casefold().strip()
        items = []
        total = 0
        start = page * page_size
        for definition in self.window._definitions.values():
            source = definition.source_type
            mine = definition.is_favorite or source in {"custom", "creator_grid", "imported_pack", "plugin_pack", "legacy_pack"}
            if category == "my" and not mine: continue
            if category == "favorites" and not definition.is_favorite: continue
            if category == "creator" and source != "creator_grid": continue
            if category == "imports" and source not in {"imported_pack", "plugin_pack", "legacy_pack"}: continue
            if category == "custom" and source != "custom": continue
            if needle and needle not in " ".join((definition.display_name, definition.family, source, *definition.tags)).casefold(): continue
            if start <= total < start + page_size:
                items.append(self.window._style_payload(definition))
            total += 1
        return {"styles": items, "total": total, "page": page}

    @staticmethod
    def _with_suffix(path: str, suffix: str) -> str:
        result = Path(path)
        return str(result if result.suffix.lower() == suffix else result.with_suffix(suffix))

    @staticmethod
    def _creator_model(raw: object) -> CreatorCrosshair:
        if not isinstance(raw, dict) or len(raw) > 12:
            raise ValueError("Invalid creator model")
        allowed = {"format", "version", "name", "grid_size", "creation_mode", "color_hex", "filled_cells", "style_id", "created_at", "updated_at"}
        if set(raw) - allowed:
            raise ValueError("Unknown creator model fields")
        cells = raw.get("filled_cells", [])
        if not isinstance(cells, list) or len(cells) > 4096:
            raise ValueError("Creator grid is too large")
        return CreatorCrosshair.from_dict(raw)

    @staticmethod
    def _zoom_settings(raw: dict) -> BetaZoomSettings:
        string_fields = {"hotkeySequence": "hotkey_sequence", "displayMode": "display_mode", "targetMonitorId": "target_monitor_id"}
        bool_fields = {"sidebarEnabled": "sidebar_enabled", "liveEnabled": "live_enabled", "zoomEnabled": "zoom_enabled", "animationEnabled": "animation_enabled"}
        int_fields = {"positionXPercent": ("position_x_percent", 0, 100), "positionYPercent": ("position_y_percent", 0, 100), "zoomPercent": ("zoom_percent", 200, 10000), "animationDurationMs": ("animation_duration_ms", 0, 5000)}
        values = {}
        for name, field in string_fields.items():
            value = raw[name]
            if not isinstance(value, str) or len(value) > 128: raise ValueError(f"Invalid {name}")
            values[field] = value
        if values["display_mode"] not in {"monitor", "crosshair"}: raise ValueError("Unsupported zoom display mode")
        for name, field in bool_fields.items():
            if not isinstance(raw[name], bool): raise ValueError(f"Invalid {name}")
            values[field] = raw[name]
        for name, (field, minimum, maximum) in int_fields.items():
            value = raw[name]
            if type(value) is not int or not minimum <= value <= maximum: raise ValueError(f"Invalid {name}")
            values[field] = value
        return BetaZoomSettings(**values)

