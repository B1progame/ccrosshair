from __future__ import annotations

import re
import json
from dataclasses import replace
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..app_metadata import APP_VERSION
from ..app_settings import BetaZoomSettings
from ..creator.models import CreatorCrosshair
from ..crosshairs.models import CrosshairDefinition, SettingKind, style_with_updates
from ..hotkey_utils import parse_hotkey


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
        "updateGameLoadouts": {"gameId", "loadouts", "activeLoadoutId"},
        "selectGameLoadout": {"gameId", "loadoutId"},
        "importGame": set(), "rescanGames": set(), "setZoom": {"settings": {"sidebarEnabled", "liveEnabled", "zoomEnabled", "hotkeySequence", "activationMode", "displayMode", "targetMonitorId", "positionXPercent", "positionYPercent", "zoomPercent", "runtimeMode", "autoAdaptEnabled", "zoomInHotkeySequence", "zoomOutHotkeySequence", "zoomResetHotkeySequence", "animationEnabled", "animationDurationMs", "consumeMouseWheel", "cleanupEnabled", "cleanupRadius", "cleanupStrength", "cleanupPreview", "hideCrosshairWhenZoomed"}}, "setTypingState": {"active"},
        "chooseStorage": set(), "checkUpdates": set(), "resetSettings": set(), "exportDiagnostics": set(),
        "previewSettingsBackup": set(), "restoreSettingsBackup": {"fingerprint"},
        "runCompatibilityCheck": set(),
        "setAccessibility": {"settings"}, "setReactive": {"settings"},
        "setLoadoutHotkeys": {"nextHotkey", "previousHotkey", "favoriteHotkey"},
        "setMonitorOffset": {"monitorId", "x", "y"},
        "setLibraryMetadata": {"collections", "tags"}, "findDuplicates": set(),
    }
    PAGES = {"home", "library", "my_crosshairs", "creator", "games", "zoom", "export", "settings", "about", "detail", "compatibility"}
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
        if command == "findDuplicates": return self._find_duplicates()
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
        if command == "setAccessibility":
            w.accessibility_changed.emit(self._accessibility_settings(payload["settings"]))
            return {"accepted": True}
        if command == "setReactive":
            w.reactive_settings_changed.emit(self._reactive_settings(payload["settings"]))
            return {"accepted": True}
        if command == "setLoadoutHotkeys":
            values = [payload["nextHotkey"], payload["previousHotkey"], payload["favoriteHotkey"]]
            if any(not isinstance(value, str) or len(value) > 128 or parse_hotkey(value) is None for value in values):
                raise ValueError("Each quick-switch shortcut must be a valid key combination")
            normalized = [parse_hotkey(value).sequence for value in values]
            if len(set(value.casefold() for value in normalized)) != 3:
                raise ValueError("Quick-switch shortcuts must be different")
            w.loadout_hotkeys_changed.emit(*normalized)
            return {"accepted": True}
        if command == "setMonitorOffset":
            monitor_id, x, y = payload["monitorId"], payload["x"], payload["y"]
            if not isinstance(monitor_id, str) or not monitor_id or len(monitor_id) > 64 or type(x) is not int or type(y) is not int or not -128 <= x <= 128 or not -128 <= y <= 128:
                raise ValueError("Monitor offset must identify a display and stay within ±128 pixels")
            if monitor_id not in {item[0] for item in w._beta_monitors}:
                raise ValueError("Unknown monitor calibration target")
            w.monitor_offset_changed.emit(monitor_id, x, y)
            return {"accepted": True}
        if command == "setLibraryMetadata":
            collections, tags = self._library_metadata(payload["collections"], payload["tags"], w._definitions)
            w.library_metadata_changed.emit(collections, tags)
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
                handler = getattr(w, "creator_save_handler", None)
                if not callable(handler):
                    raise RuntimeError("Creator saving is unavailable")
                return handler(model, payload["activate"])
            path, _ = QFileDialog.getSaveFileName(w, "Export Creator Crosshair", f"{model.name or 'crosshair'}.chgrid", "Creator crosshair (*.chgrid)")
            if path: w.creator_export_requested.emit(model, self._with_suffix(path, ".chgrid"))
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "setGameProfile":
            game_id, style_id, enabled = payload["gameId"], payload["styleId"], payload["enabled"]
            if not isinstance(game_id, str) or not game_id or len(game_id) > 256 or (style_id and style_id not in w._definitions) or not isinstance(enabled, bool): raise ValueError("Invalid game profile")
            w.game_profile_updated.emit(game_id, style_id, enabled); return {"accepted": True}
        if command == "updateGameLoadouts":
            game_id, loadouts, active_id = payload["gameId"], payload["loadouts"], payload["activeLoadoutId"]
            normalized = self._game_loadouts(loadouts, w._definitions)
            if not isinstance(game_id, str) or not game_id or len(game_id) > 256 or not isinstance(active_id, str):
                raise ValueError("Invalid game loadout profile")
            if normalized and active_id not in {item["loadout_id"] for item in normalized}:
                raise ValueError("Active loadout does not exist")
            w.game_loadouts_updated.emit(game_id, normalized, active_id)
            return {"accepted": True}
        if command == "selectGameLoadout":
            game_id, loadout_id = payload["gameId"], payload["loadoutId"]
            if not isinstance(game_id, str) or not game_id or len(game_id) > 256 or not isinstance(loadout_id, str) or not loadout_id:
                raise ValueError("Invalid selected game loadout")
            profile = next((item for item in w._games_data if item.game_id == game_id), None)
            if profile is None or loadout_id not in {item["loadout_id"] for item in profile.loadouts}:
                raise ValueError("Unknown game loadout")
            w.game_loadout_selected.emit(game_id, loadout_id)
            return {"accepted": True}
        if command == "importGame":
            path, _ = QFileDialog.getOpenFileName(w, "Add Game Executable", "", "Applications (*.exe)")
            if path: w.import_game_requested.emit(path)
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "rescanGames": w.rescan_games_requested.emit(); return {"accepted": True}
        if command == "setZoom":
            w.beta_zoom_settings_changed.emit(self._zoom_settings(payload["settings"]))
            return {"accepted": True}
        if command == "setTypingState":
            if not isinstance(payload["active"], bool): raise ValueError("Typing state must be a boolean")
            w.keyboard_entry_active = payload["active"]
            return {"accepted": True}
        if command == "chooseStorage":
            path = QFileDialog.getExistingDirectory(w, "Crosshair Storage Folder", w._storage_path)
            if path: w.storage_path_changed.emit(path)
            return {"accepted": bool(path), "cancelled": not bool(path)}
        if command == "checkUpdates": w.check_updates_requested.emit(); return {"accepted": True}
        if command == "resetSettings": w.reset_requested.emit(); return {"accepted": True}
        if command == "previewSettingsBackup":
            handler = getattr(w, "settings_backup_preview_handler", None)
            if not callable(handler):
                return {"available": False, "reason": "Settings backup preview is unavailable."}
            return handler()
        if command == "restoreSettingsBackup":
            fingerprint = payload["fingerprint"]
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                raise ValueError("Invalid settings backup preview token")
            handler = getattr(w, "settings_backup_restore_handler", None)
            if not callable(handler):
                raise RuntimeError("Settings backup restore is unavailable")
            return handler(fingerprint)
        if command == "runCompatibilityCheck":
            handler = getattr(w, "compatibility_check_handler", None)
            if not callable(handler):
                raise RuntimeError("The monitor capture check is unavailable")
            return handler()
        if command == "exportDiagnostics":
            diagnostics = dict(w._zoom_diagnostics)
            report = {
                "format": "crosshair-overlay-diagnostics-v1",
                "appVersion": APP_VERSION,
                "runtime": "Windows desktop / Qt screen capture",
                "zoom": {
                    "enabled": bool(w._beta_zoom_settings.zoom_enabled or w._beta_zoom_settings.live_enabled),
                    "mode": w._beta_zoom_settings.runtime_mode,
                    "backend": str(diagnostics.get("backend", "not measured")),
                    "model": str(diagnostics.get("model", "none")),
                    "captureWidth": int(diagnostics.get("captureWidth", 0) or 0),
                    "captureHeight": int(diagnostics.get("captureHeight", 0) or 0),
                    "outputFps": float(diagnostics.get("outputFps", 0) or 0),
                    "frameAgeP50Ms": float(diagnostics.get("frameAgeP50Ms", 0) or 0),
                    "frameAgeP95Ms": float(diagnostics.get("frameAgeP95Ms", 0) or 0),
                    "processingMs": float(diagnostics.get("processingMs", 0) or 0),
                    "droppedFrames": int(diagnostics.get("droppedFrames", 0) or 0),
                    "frames": int(diagnostics.get("frames", 0) or 0),
                    "effectiveZoomMax": int(diagnostics.get("effectiveZoomMax", 1600) or 1600),
                    "cleanupStatus": str(diagnostics.get("cleanup", "disabled")),
                    "cleanupConfidence": float(diagnostics.get("cleanupConfidence", 0) or 0),
                },
                "configurationSummary": {
                    "crosshairOverlayEnabled": bool(w._overlay_status),
                    "reactiveInputEnabled": bool(w._reactive_settings.enabled),
                    "reducedMotion": bool(w._accessibility_settings.reduced_motion),
                },
                "privacy": "No captured frames, game names, usernames, filesystem paths, or credentials are included.",
            }
            preview = json.dumps(report, ensure_ascii=False, indent=2)
            answer = QMessageBox.question(w, "Preview diagnostics export", preview + "\n\nSave this sanitized report?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Save:
                return {"accepted": False, "cancelled": True}
            path, _ = QFileDialog.getSaveFileName(w, "Save diagnostics report", "crosshair-diagnostics.json", "JSON report (*.json)")
            if not path:
                return {"accepted": False, "cancelled": True}
            Path(path).write_text(preview, encoding="utf-8")
            return {"accepted": True}
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
            if key == "outlineColor":
                if "outline_rgba" not in specs or not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value): raise ValueError("Outline color is invalid or not editable")
                color = QColor(value)
                alpha = definition.style.outline_rgba[3]
                updates["outline_rgba"] = (color.red(), color.green(), color.blue(), alpha)
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
        supported_categories = {"all", "my", "favorites", "creator", "imports", "custom", "recent"}
        known_collection = (isinstance(category, str) and category.startswith("collection:")
                            and category[11:] in {item["id"] for item in getattr(self.window, "_library_collections", [])})
        if not isinstance(query, str) or len(query) > 256 or not isinstance(category, str) or (category not in supported_categories and not known_collection):
            raise ValueError("Invalid catalog query")
        if type(page) is not int or not 0 <= page <= 10000 or type(page_size) is not int or not 1 <= page_size <= 48:
            raise ValueError("Catalog page is out of range")
        needle = query.casefold().strip()
        items = []
        total = 0
        start = page * page_size
        definitions = list(self.window._definitions.values())
        tokens = [token for token in needle.split() if token]
        collection_styles: set[str] | None = None
        if category.startswith("collection:"):
            collection = next(item for item in getattr(self.window, "_library_collections", []) if item["id"] == category[11:])
            collection_styles = set(collection["styleIds"])
            definitions = [item for item in definitions if item.style_id in collection_styles]
        if category == "recent":
            recent_ids = list(getattr(self.window, "_recent_style_ids", []))
            rank = {style_id: index for index, style_id in enumerate(recent_ids)}
            definitions = [item for item in definitions if item.style_id in rank]
            definitions.sort(key=lambda item: rank[item.style_id])
        for definition in definitions:
            source = definition.source_type
            mine = definition.is_favorite or source in {"custom", "creator_grid", "imported_pack", "plugin_pack", "legacy_pack"}
            if category == "my" and not mine: continue
            if category == "favorites" and not definition.is_favorite: continue
            if category == "creator" and source != "creator_grid": continue
            if category == "imports" and source not in {"imported_pack", "plugin_pack", "legacy_pack"}: continue
            if category == "custom" and source != "custom": continue
            if collection_styles is not None and definition.style_id not in collection_styles: continue
            searchable = getattr(definition, "searchable_text", None)
            if searchable is None:
                searchable = " ".join(str(value) for value in (
                    getattr(definition, "display_name", ""), getattr(definition, "family", ""),
                    source, getattr(definition, "description", ""), getattr(definition, "origin_game", ""),
                    getattr(definition, "author", ""), *getattr(definition, "aliases", ()),
                    *getattr(definition, "tags", ()),
                )).casefold()
            custom_tags = getattr(self.window, "_library_tags", {}).get(definition.style_id, [])
            if custom_tags:
                searchable += " " + " ".join(custom_tags).casefold()
            if tokens and not all(token in searchable for token in tokens): continue
            if start <= total < start + page_size:
                items.append(self.window._style_payload(definition))
            total += 1
        return {"styles": items, "total": total, "page": page}

    @staticmethod
    def _library_metadata(raw_collections: object, raw_tags: object, definitions: dict) -> tuple[list[dict], dict[str, list[str]]]:
        if not isinstance(raw_collections, list) or len(raw_collections) > 50 or not isinstance(raw_tags, dict) or len(raw_tags) > 10000:
            raise ValueError("Library metadata exceeds its size limit")
        collections: list[dict] = []
        collection_ids: set[str] = set()
        names: set[str] = set()
        for item in raw_collections:
            if not isinstance(item, dict) or set(item) != {"id", "name", "styleIds"}:
                raise ValueError("Collection data is malformed")
            collection_id, name, style_ids = item["id"], item["name"], item["styleIds"]
            if (not isinstance(collection_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,64}", collection_id)
                    or collection_id in collection_ids or not isinstance(name, str) or not name.strip()
                    or len(name.strip()) > 64 or name.strip().casefold() in names
                    or not isinstance(style_ids, list) or len(style_ids) > 500
                    or any(not isinstance(style_id, str) or style_id not in definitions for style_id in style_ids)
                    or len(set(style_ids)) != len(style_ids)):
                raise ValueError("Collection name or style selection is invalid")
            collection_ids.add(collection_id)
            names.add(name.strip().casefold())
            collections.append({"id": collection_id, "name": name.strip(), "styleIds": list(style_ids)})
        tags: dict[str, list[str]] = {}
        total_tags = 0
        for style_id, raw_values in raw_tags.items():
            if not isinstance(style_id, str) or style_id not in definitions or not isinstance(raw_values, list) or len(raw_values) > 32:
                raise ValueError("Tag assignment refers to an unknown style or is too large")
            values: list[str] = []
            for value in raw_values:
                if not isinstance(value, str) or not value.strip() or len(value.strip()) > 32:
                    raise ValueError("Tags must contain 1–32 characters")
                normalized = value.strip().casefold()
                if normalized not in values:
                    values.append(normalized)
            if values:
                total_tags += len(values)
                if total_tags > 10000:
                    raise ValueError("Library tag assignments exceed their size limit")
                tags[style_id] = values
        return collections, tags

    def _find_duplicates(self) -> list[dict]:
        groups: dict[tuple, list[CrosshairDefinition]] = {}
        for item in self.window._definitions.values():
            style = item.style
            signature = (getattr(style.shape, "value", style.shape), style.arm_length, style.gap, style.thickness,
                         style.center_dot, style.center_dot_size, style.circle_radius, style.circle_thickness,
                         style.custom_grid_size, tuple(style.custom_filled_cells), style.custom_cell_size,
                         style.t_style, style.rotation_degrees)
            groups.setdefault(signature, []).append(item)
        return [{"styleIds": [item.style_id for item in items],
                 "names": [item.display_name for item in items]}
                for items in groups.values() if len(items) > 1][:200]

    @staticmethod
    def _with_suffix(path: str, suffix: str) -> str:
        result = Path(path)
        return str(result if result.suffix.lower() == suffix else result.with_suffix(suffix))

    @staticmethod
    def _game_loadouts(raw: object, definitions: dict[str, CrosshairDefinition]) -> list[dict]:
        fields = {"loadout_id", "name", "style_id", "zoom_percent", "fire_pulse", "fire_cadence_ms", "fire_key_sequence", "gap_expansion",
                  "opacity_pulse", "hide_on_ads", "fire_duration_ms", "fire_amplitude_percent", "ads_transition_ms",
                  "color_hex", "opacity_percent", "outline_color_hex", "outline_opacity_percent", "ads_style_id",
                  "ads_color_hex", "ads_opacity_percent", "ads_outline_color_hex", "ads_outline_opacity_percent"}
        if not isinstance(raw, list) or len(raw) > 20:
            raise ValueError("A game profile can have at most 20 loadouts")
        result: list[dict] = []
        seen: set[str] = set()
        bounds = {"zoom_percent": (200, 1600), "fire_duration_ms": (40, 1000), "fire_cadence_ms": (0, 1000),
                  "fire_amplitude_percent": (0, 100), "ads_transition_ms": (0, 500),
                  "opacity_percent": (0, 100), "outline_opacity_percent": (0, 100),
                  "ads_opacity_percent": (0, 100), "ads_outline_opacity_percent": (0, 100)}
        bools = {"fire_pulse", "gap_expansion", "opacity_pulse", "hide_on_ads"}
        for item in raw:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError("Malformed game loadout")
            loadout_id, name, style_id = item["loadout_id"], item["name"], item["style_id"]
            if (not isinstance(loadout_id, str) or not loadout_id or len(loadout_id) > 64 or loadout_id in seen
                    or not isinstance(name, str) or not name.strip() or len(name) > 64
                    or not isinstance(style_id, str) or style_id not in definitions):
                raise ValueError("Invalid or duplicate game loadout")
            seen.add(loadout_id)
            normalized = {"loadout_id": loadout_id, "name": name.strip(), "style_id": style_id}
            ads_style_id = item["ads_style_id"]
            if not isinstance(ads_style_id, str) or (ads_style_id and ads_style_id not in definitions):
                raise ValueError("Invalid ADS style")
            normalized["ads_style_id"] = ads_style_id
            fire_key = item["fire_key_sequence"]
            if not isinstance(fire_key, str) or len(fire_key) > 128 or (fire_key.strip() and parse_hotkey(fire_key) is None):
                raise ValueError("Invalid loadout fire key")
            normalized["fire_key_sequence"] = parse_hotkey(fire_key).sequence if fire_key.strip() else ""
            for key, (minimum, maximum) in bounds.items():
                value = item[key]
                if type(value) is not int or not minimum <= value <= maximum:
                    raise ValueError(f"Invalid loadout {key}")
                normalized[key] = value
            for key in bools:
                if type(item[key]) is not bool:
                    raise ValueError(f"Invalid loadout {key}")
                normalized[key] = item[key]
            for key in ("color_hex", "outline_color_hex", "ads_color_hex", "ads_outline_color_hex"):
                value = item[key]
                if not isinstance(value, str) or (value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value)):
                    raise ValueError(f"Invalid loadout {key}")
                normalized[key] = value.upper()
            result.append(normalized)
        return result

    @staticmethod
    def _creator_model(raw: object) -> CreatorCrosshair:
        if not isinstance(raw, dict) or len(raw) > 13:
            raise ValueError("Invalid creator model")
        allowed = {"format", "version", "name", "grid_size", "creation_mode", "color_hex", "filled_cells", "style_id", "created_at", "updated_at", "layers"}
        if set(raw) - allowed:
            raise ValueError("Unknown creator model fields")
        if raw.get("format") not in {"crosshair-overlay-creator-v2", "crosshair-overlay-creator-v3"}:
            raise ValueError("Unsupported creator format")
        grid_size = raw.get("grid_size")
        if type(grid_size) is not int or not 8 <= grid_size <= 64:
            raise ValueError("Creator grid size is invalid")
        cells = raw.get("filled_cells", [])
        if not isinstance(cells, list) or len(cells) > 4096:
            raise ValueError("Creator grid is too large")
        for cell in cells:
            if not isinstance(cell, list) or len(cell) != 2 or any(type(value) is not int or not 0 <= value < grid_size for value in cell):
                raise ValueError("Creator cell is outside the grid")
        layers = raw.get("layers", [])
        if not isinstance(layers, list) or len(layers) > 32:
            raise ValueError("Creator has too many layers")
        layer_ids: set[str] = set()
        for layer in layers:
            if not isinstance(layer, dict) or set(layer) != {"id", "name", "primitive", "visible", "filled_cells"}:
                raise ValueError("Creator layer is malformed")
            if (not isinstance(layer["id"], str) or not layer["id"] or len(layer["id"]) > 64 or layer["id"] in layer_ids
                    or not isinstance(layer["name"], str) or not layer["name"].strip() or len(layer["name"]) > 64
                    or layer["primitive"] not in {"draw", "cross", "dot", "ring", "bracket"}
                    or not isinstance(layer["visible"], bool) or not isinstance(layer["filled_cells"], list) or len(layer["filled_cells"]) > 4096):
                raise ValueError("Creator layer settings are invalid")
            layer_ids.add(layer["id"])
            if any(not isinstance(cell, list) or len(cell) != 2 or any(type(value) is not int or not 0 <= value < grid_size for value in cell) for cell in layer["filled_cells"]):
                raise ValueError("Creator layer cell is outside the grid")
        return CreatorCrosshair.from_dict(raw)

    @staticmethod
    def _zoom_settings(raw: dict) -> BetaZoomSettings:
        string_fields = {"hotkeySequence": "hotkey_sequence", "activationMode": "activation_mode", "displayMode": "display_mode", "targetMonitorId": "target_monitor_id", "runtimeMode": "runtime_mode", "zoomInHotkeySequence": "zoom_in_hotkey_sequence", "zoomOutHotkeySequence": "zoom_out_hotkey_sequence", "zoomResetHotkeySequence": "zoom_reset_hotkey_sequence"}
        bool_fields = {"sidebarEnabled": "sidebar_enabled", "liveEnabled": "live_enabled", "zoomEnabled": "zoom_enabled", "autoAdaptEnabled": "auto_adapt_enabled", "animationEnabled": "animation_enabled", "consumeMouseWheel": "consume_mouse_wheel", "cleanupEnabled": "cleanup_enabled", "cleanupPreview": "cleanup_preview", "hideCrosshairWhenZoomed": "hide_crosshair_when_zoomed"}
        int_fields = {"positionXPercent": ("position_x_percent", 0, 100), "positionYPercent": ("position_y_percent", 0, 100), "zoomPercent": ("zoom_percent", 200, 1600), "animationDurationMs": ("animation_duration_ms", 0, 5000), "cleanupRadius": ("cleanup_radius", 1, 24), "cleanupStrength": ("cleanup_strength", 0, 100)}
        values = {}
        for name, field in string_fields.items():
            value = raw[name]
            if not isinstance(value, str) or len(value) > 128: raise ValueError(f"Invalid {name}")
            values[field] = value
        if values["display_mode"] not in {"monitor", "crosshair"}: raise ValueError("Unsupported zoom display mode")
        if values["activation_mode"] not in {"hold", "toggle"}: raise ValueError("Unsupported Zoom activation mode")
        if values["runtime_mode"] not in {"quiet", "eco", "fast", "balanced", "quality"}: raise ValueError("Unsupported zoom runtime mode")
        for name, field in bool_fields.items():
            if not isinstance(raw[name], bool): raise ValueError(f"Invalid {name}")
            values[field] = raw[name]
        for name, (field, minimum, maximum) in int_fields.items():
            value = raw[name]
            if type(value) is not int or not minimum <= value <= maximum: raise ValueError(f"Invalid {name}")
            values[field] = value
        return BetaZoomSettings(**values)

    @staticmethod
    def _accessibility_settings(raw: object):
        from ..app_settings import AccessibilitySettings
        if not isinstance(raw, dict) or set(raw) != {"highContrast", "reducedMotion", "density", "textScale"}:
            raise ValueError("Invalid accessibility settings")
        if type(raw["highContrast"]) is not bool or type(raw["reducedMotion"]) is not bool:
            raise ValueError("Accessibility toggles must be boolean")
        if raw["density"] not in {"compact", "comfortable", "spacious"}:
            raise ValueError("Unsupported interface density")
        if type(raw["textScale"]) is not int or not 80 <= raw["textScale"] <= 150:
            raise ValueError("Text scale must be between 80 and 150 percent")
        return AccessibilitySettings(raw["highContrast"], raw["reducedMotion"], raw["density"], raw["textScale"])

    @staticmethod
    def _reactive_settings(raw: object):
        from ..app_settings import ReactiveSettings
        if not isinstance(raw, dict):
            raise ValueError("Invalid input-reactive settings")
        fields = {"enabled", "firePulse", "fireCadenceMs", "fireKeySequence", "gapExpansion", "opacityPulse", "hideOnAds",
                  "emergencyHotkey", "fireDurationMs", "fireAmplitudePercent", "adsTransitionMs", "adsMode"}
        if set(raw) != fields:
            raise ValueError("Invalid input-reactive settings")
        for key in ("enabled", "firePulse", "gapExpansion", "opacityPulse", "hideOnAds"):
            if type(raw[key]) is not bool: raise ValueError(f"{key} must be boolean")
        hotkey = raw["emergencyHotkey"]
        if not isinstance(hotkey, str) or len(hotkey) > 128: raise ValueError("Emergency hotkey is invalid")
        fire_key = raw["fireKeySequence"]
        if not isinstance(fire_key, str) or len(fire_key) > 128 or (fire_key.strip() and parse_hotkey(fire_key) is None):
            raise ValueError("Fire key is invalid")
        if not isinstance(raw["adsMode"], str) or raw["adsMode"] not in {"hold", "toggle"}: raise ValueError("ADS mode must be hold or toggle")
        ranges = {"fireCadenceMs": (0, 1000), "fireDurationMs": (40, 1000), "fireAmplitudePercent": (0, 100), "adsTransitionMs": (0, 500)}
        values = {}
        for key, (minimum, maximum) in ranges.items():
            value = raw[key]
            if type(value) is not int or not minimum <= value <= maximum: raise ValueError(f"{key} is out of range")
            values[key] = value
        return ReactiveSettings(enabled=raw["enabled"], fire_pulse=raw["firePulse"],
                                fire_cadence_ms=values["fireCadenceMs"], gap_expansion=raw["gapExpansion"],
                                fire_key_sequence=parse_hotkey(fire_key).sequence if fire_key.strip() else "",
                                opacity_pulse=raw["opacityPulse"], hide_on_ads=raw["hideOnAds"],
                                emergency_hotkey=hotkey.strip(), fire_duration_ms=values["fireDurationMs"],
                                fire_amplitude_percent=values["fireAmplitudePercent"],
                                ads_transition_ms=values["adsTransitionMs"], ads_mode=raw["adsMode"])
