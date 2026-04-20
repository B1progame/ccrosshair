from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...config import OverlayStyle
from ...creator.conversion import creator_to_overlay_style
from ...creator.editor_widget import GridEditorWidget
from ...creator.models import CreatorCrosshair
from ...overlay_renderer import draw_overlay_style
from ..components import PageHeader


class CrosshairPreviewWidget(QWidget):
    def __init__(self, background_hex: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._background = QColor(background_hex)
        self._style: OverlayStyle | None = None
        self._title = title
        self.setMinimumSize(180, 150)

    def set_overlay_style(self, style: OverlayStyle) -> None:
        self._style = style
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background)
        if self._style is not None:
            draw_overlay_style(painter, self.rect(), self._style.scaled(220))


class CreatorPage(QWidget):
    save_requested = Signal(object, bool)
    export_requested = Signal(object, str)
    status_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._name_input = QLineEdit("My Crosshair", self)
        self._mode_combo = QComboBox(self)
        self._resolution_combo = QComboBox(self)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._zoom_label = QLabel("100%", self)
        self._color_input = QLineEdit("#FFFFFF", self)
        self._color_swatch = QLabel(self)
        self._color_button = QPushButton("Pick", self)
        self._draw_tool = QToolButton(self)
        self._erase_tool = QToolButton(self)
        self._line_tool = QToolButton(self)
        self._brush_spin = QSpinBox(self)
        self._grid = GridEditorWidget(grid_size=32, parent=self)
        self._undo_button = QPushButton("Undo", self)
        self._redo_button = QPushButton("Redo", self)
        self._clear_button = QPushButton("Clear", self)
        self._new_button = QPushButton("New", self)
        self._save_button = QPushButton("Save to Library", self)
        self._save_use_button = QPushButton("Save & Use", self)
        self._export_button = QPushButton("Export", self)
        self._show_grid = QCheckBox("Grid", self)
        self._mirror_x = QCheckBox("Mirror X", self)
        self._mirror_y = QCheckBox("Mirror Y", self)
        self._keep_on_resize = QCheckBox("Scale drawing on resolution change", self)
        self._hover_label = QLabel("-", self)
        self._anchor_label = QLabel("Line: idle", self)
        self._preview_neutral = CrosshairPreviewWidget("#242A36", "Neutral", self)
        self._preview_dark = CrosshairPreviewWidget("#0D1320", "Dark", self)
        self._preview_light = CrosshairPreviewWidget("#EEF2F8", "Light", self)
        self._status = QLabel("Ready", self)
        self._dirty = False
        self._current_mode = "draw"
        self._build_ui()
        self._wire_signals()
        self._install_shortcuts()
        self._load_defaults()
        self._on_undo_redo_changed(self._grid.can_undo(), self._grid.can_redo())
        self._refresh_preview()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Creator Studio",
                "Create custom crosshairs with drawing and pixel-grid workflows that match the rest of the redesigned app.",
                eyebrow="Creator",
                parent=self,
            )
        )

        header = QFrame(self)
        header.setObjectName("HeroCard")
        header_layout = QGridLayout()
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setHorizontalSpacing(14)
        header_layout.setVerticalSpacing(12)
        header_layout.addWidget(QLabel("Crosshair Name", self), 0, 0)
        header_layout.addWidget(self._name_input, 1, 0, 1, 2)
        header_layout.addWidget(QLabel("Mode", self), 0, 2)
        header_layout.addWidget(self._mode_combo, 1, 2)
        header_layout.addWidget(QLabel("Resolution", self), 0, 3)
        header_layout.addWidget(self._resolution_combo, 1, 3)
        header_layout.addWidget(QLabel("Color", self), 0, 4)
        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        self._color_swatch.setFixedSize(26, 26)
        self._color_swatch.setObjectName("ColorSwatch")
        color_row.addWidget(self._color_swatch)
        color_row.addWidget(self._color_input)
        color_row.addWidget(self._color_button)
        color_widget = QWidget(self)
        color_widget.setLayout(color_row)
        header_layout.addWidget(color_widget, 1, 4)
        header.setLayout(header_layout)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        left_panel = QFrame(self)
        left_panel.setObjectName("Card")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)
        left_layout.addWidget(QLabel("Tools", self))

        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        for button, label in (
            (self._draw_tool, "Draw"),
            (self._erase_tool, "Erase"),
            (self._line_tool, "Line"),
        ):
            button.setText(label)
            button.setCheckable(True)
            button.setMinimumHeight(36)
            tool_row.addWidget(button)
        left_layout.addLayout(tool_row)

        brush_row = QHBoxLayout()
        brush_row.addWidget(QLabel("Brush Size", self))
        self._brush_spin.setRange(1, 8)
        brush_row.addStretch(1)
        brush_row.addWidget(self._brush_spin)
        left_layout.addLayout(brush_row)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Canvas Zoom", self))
        self._zoom_slider.setRange(60, 160)
        self._zoom_slider.setSingleStep(5)
        zoom_row.addWidget(self._zoom_slider, 1)
        zoom_row.addWidget(self._zoom_label)
        left_layout.addLayout(zoom_row)

        options = QGridLayout()
        options.setHorizontalSpacing(8)
        options.setVerticalSpacing(8)
        self._show_grid.setChecked(True)
        self._keep_on_resize.setChecked(True)
        options.addWidget(self._show_grid, 0, 0)
        options.addWidget(self._mirror_x, 0, 1)
        options.addWidget(self._mirror_y, 1, 0)
        options.addWidget(self._keep_on_resize, 1, 1)
        left_layout.addLayout(options)

        info_card = QFrame(self)
        info_card.setObjectName("SubtleCard")
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(6)
        info_layout.addWidget(QLabel("Workspace Feedback", self))
        self._hover_label.setObjectName("Muted")
        self._anchor_label.setObjectName("Muted")
        info_layout.addWidget(QLabel("Cursor Cell", self))
        info_layout.addWidget(self._hover_label)
        info_layout.addWidget(QLabel("Line Tool", self))
        info_layout.addWidget(self._anchor_label)
        info_card.setLayout(info_layout)
        left_layout.addWidget(info_card)
        left_layout.addStretch(1)
        left_panel.setLayout(left_layout)
        body.addWidget(left_panel, 2)

        canvas_panel = QFrame(self)
        canvas_panel.setObjectName("EditorCanvasCard")
        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(16, 16, 16, 16)
        canvas_layout.setSpacing(12)
        canvas_head = QHBoxLayout()
        canvas_head.addWidget(QLabel("Editor Canvas", self))
        mode_hint = QLabel("Free drawing for sketching, Pixel Art for crisp low-res shapes.", self)
        mode_hint.setObjectName("Muted")
        canvas_head.addStretch(1)
        canvas_head.addWidget(mode_hint)
        canvas_layout.addLayout(canvas_head)
        canvas_layout.addWidget(self._grid, 1)
        canvas_panel.setLayout(canvas_layout)
        body.addWidget(canvas_panel, 5)

        right_panel = QFrame(self)
        right_panel.setObjectName("Card")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)
        right_layout.addWidget(QLabel("Live Preview", self))
        right_layout.addWidget(self._preview_neutral)
        right_layout.addWidget(self._preview_dark)
        right_layout.addWidget(self._preview_light)
        right_layout.addStretch(1)
        right_panel.setLayout(right_layout)
        body.addWidget(right_panel, 2)
        root.addLayout(body, 1)

        footer = QFrame(self)
        footer.setObjectName("Card")
        footer_layout = QVBoxLayout()
        footer_layout.setContentsMargins(16, 16, 16, 16)
        footer_actions = QHBoxLayout()
        footer_actions.setSpacing(8)
        self._save_button.setObjectName("PrimaryButton")
        self._save_use_button.setObjectName("PrimaryButton")
        footer_actions.addWidget(self._new_button)
        footer_actions.addWidget(self._clear_button)
        footer_actions.addWidget(self._undo_button)
        footer_actions.addWidget(self._redo_button)
        footer_actions.addStretch(1)
        footer_actions.addWidget(self._save_button)
        footer_actions.addWidget(self._save_use_button)
        footer_actions.addWidget(self._export_button)
        footer_layout.addLayout(footer_actions)
        self._status.setObjectName("Muted")
        footer_layout.addWidget(self._status)
        footer.setLayout(footer_layout)
        root.addWidget(footer)

        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._draw_tool.clicked.connect(self._activate_draw_tool)
        self._erase_tool.clicked.connect(self._activate_erase_tool)
        self._line_tool.clicked.connect(self._activate_line_tool)
        self._brush_spin.valueChanged.connect(self._on_brush_changed)
        self._show_grid.toggled.connect(self._grid.set_show_grid)
        self._mirror_x.toggled.connect(self._on_mirror_changed)
        self._mirror_y.toggled.connect(self._on_mirror_changed)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self._color_button.clicked.connect(self._pick_color)
        self._color_input.editingFinished.connect(self._apply_color_text)
        self._name_input.textChanged.connect(lambda _: self._set_dirty(True))
        self._grid.state_changed.connect(self._on_editor_state_changed)
        self._grid.undo_redo_changed.connect(self._on_undo_redo_changed)
        self._grid.line_anchor_changed.connect(self._on_line_anchor_changed)
        self._grid.hovered_cell_changed.connect(self._hover_label.setText)
        self._new_button.clicked.connect(self._new_draft)
        self._clear_button.clicked.connect(self._clear_canvas)
        self._undo_button.clicked.connect(self._grid.undo)
        self._redo_button.clicked.connect(self._grid.redo)
        self._save_button.clicked.connect(lambda: self._save(activate_now=False))
        self._save_use_button.clicked.connect(lambda: self._save(activate_now=True))
        self._export_button.clicked.connect(self._export)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._grid.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._grid.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self._grid.redo)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=lambda: self._save(activate_now=False))

    def _load_defaults(self) -> None:
        self._mode_combo.addItem("Draw Mode", userData="draw")
        self._mode_combo.addItem("Pixel Art Mode", userData="pixel")
        self._zoom_slider.setValue(100)
        self._draw_tool.setChecked(True)
        self._brush_spin.setValue(1)
        self._refresh_resolution_choices("draw", selected=32)
        self._grid.set_tool("draw")
        self._update_color_swatch("#FFFFFF")

    def _refresh_resolution_choices(self, mode: str, selected: int | None = None) -> None:
        options = [24, 32, 48, 64] if mode == "draw" else [16, 24, 32, 48, 64]
        self._resolution_combo.blockSignals(True)
        self._resolution_combo.clear()
        current = selected or self._grid.grid_size()
        current_index = 0
        for idx, value in enumerate(options):
            self._resolution_combo.addItem(f"{value} x {value}", userData=value)
            if value == current:
                current_index = idx
        self._resolution_combo.setCurrentIndex(current_index)
        self._resolution_combo.blockSignals(False)

    def _activate_draw_tool(self) -> None:
        self._draw_tool.setChecked(True)
        self._erase_tool.setChecked(False)
        self._line_tool.setChecked(False)
        self._grid.set_tool("draw")
        self._set_status("Draw tool active.")

    def _activate_erase_tool(self) -> None:
        self._draw_tool.setChecked(False)
        self._erase_tool.setChecked(True)
        self._line_tool.setChecked(False)
        self._grid.set_tool("erase")
        self._set_status("Eraser active.")

    def _activate_line_tool(self) -> None:
        self._draw_tool.setChecked(False)
        self._erase_tool.setChecked(False)
        self._line_tool.setChecked(True)
        self._grid.set_tool("line")
        self._set_status("Line tool active. Click a start cell, then click an end cell.")

    def _on_brush_changed(self, value: int) -> None:
        self._grid.set_brush_size(value)
        self._set_status(f"Brush size set to {value}.")

    def _on_mirror_changed(self) -> None:
        self._grid.set_mirror(self._mirror_x.isChecked(), self._mirror_y.isChecked())

    def _on_mode_changed(self) -> None:
        mode = self._mode_combo.currentData()
        if not isinstance(mode, str):
            return
        self._current_mode = mode
        suggested = 32 if mode == "draw" else 24
        self._refresh_resolution_choices(mode, selected=suggested)
        self._set_status("Pixel Art mode prioritizes lower-resolution crisp cells." if mode == "pixel" else "Draw mode keeps a flexible sketching grid.")

    def _on_resolution_changed(self) -> None:
        value = self._resolution_combo.currentData()
        if not isinstance(value, int):
            return
        preserve = self._keep_on_resize.isChecked()
        if self._dirty and not preserve:
            answer = QMessageBox.question(
                self,
                "Change Resolution?",
                "Switching resolution without scaling will reset the current drawing. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._refresh_resolution_choices(self._current_mode, selected=self._grid.grid_size())
                return
        self._grid.set_grid_size(value, preserve=preserve)
        self._set_dirty(True)
        self._refresh_preview()
        self._set_status(f"Canvas resolution set to {value}x{value}.")

    def _on_zoom_changed(self, value: int) -> None:
        self._grid.set_zoom_percent(value)
        self._zoom_label.setText(f"{value}%")

    def _pick_color(self) -> None:
        current = QColor(self._color_input.text().strip())
        color = QColorDialog.getColor(current if current.isValid() else QColor("#FFFFFF"), self, "Choose Crosshair Color")
        if color.isValid():
            self._color_input.setText(color.name().upper())
            self._apply_color_text()

    def _apply_color_text(self) -> None:
        raw = self._color_input.text().strip()
        color = QColor(raw)
        if not color.isValid():
            color = QColor("#FFFFFF")
        normalized = color.name().upper()
        self._color_input.setText(normalized)
        self._update_color_swatch(normalized)
        self._grid.set_color_hex(normalized)
        self._refresh_preview()
        self._set_dirty(True)

    def _update_color_swatch(self, color_hex: str) -> None:
        self._color_swatch.setStyleSheet(
            f"background: {color_hex}; border: 1px solid rgba(255,255,255,0.18); border-radius: 8px;"
        )

    def _on_editor_state_changed(self) -> None:
        self._refresh_preview()
        self._set_dirty(True)

    def _on_undo_redo_changed(self, can_undo: bool, can_redo: bool) -> None:
        self._undo_button.setEnabled(can_undo)
        self._redo_button.setEnabled(can_redo)

    def _on_line_anchor_changed(self, active: bool) -> None:
        self._anchor_label.setText("Line: start selected" if active else "Line: idle")

    def _new_draft(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self._name_input.setText("My Crosshair")
        self._color_input.setText("#FFFFFF")
        self._update_color_swatch("#FFFFFF")
        self._mode_combo.setCurrentIndex(0)
        self._grid.set_color_hex("#FFFFFF")
        self._grid.set_cells(set(), reset_history=True)
        self._grid.set_grid_size(32, preserve=False)
        self._set_dirty(False)
        self._refresh_preview()
        self._set_status("Started a new draft.")

    def load_from_model(self, model: CreatorCrosshair) -> None:
        self._name_input.setText(model.name.strip() or "Imported Crosshair")
        self._color_input.setText(model.color_hex.upper())
        self._update_color_swatch(model.color_hex.upper())
        self._grid.set_color_hex(model.color_hex.upper())

        mode = model.creation_mode if model.creation_mode in {"draw", "pixel"} else "draw"
        mode_index = self._mode_combo.findData(mode)
        self._mode_combo.setCurrentIndex(max(0, mode_index))

        self._refresh_resolution_choices(mode, selected=model.grid_size)
        res_index = self._resolution_combo.findData(model.grid_size)
        if res_index >= 0:
            self._resolution_combo.setCurrentIndex(res_index)
        self._grid.set_grid_size(model.grid_size, preserve=False)
        self._grid.set_cells(set(model.normalized_cells()), reset_history=True)
        self._set_dirty(False)
        self._refresh_preview()
        self._set_status(f"Loaded '{model.name}' into Creator.")

    def _clear_canvas(self) -> None:
        self._grid.clear_canvas()
        self._set_status("Canvas cleared.")

    def _save(self, activate_now: bool) -> None:
        model = self._build_model(validate_name=True)
        if model is None:
            return
        if not model.filled_cells:
            QMessageBox.warning(self, "Nothing to Save", "Draw at least one cell before saving.")
            return
        self.save_requested.emit(model, activate_now)
        self._set_dirty(False)
        self._set_status(f"Saved '{model.name}' to library.")

    def _export(self) -> None:
        model = self._build_model(validate_name=True)
        if model is None:
            return
        if not model.filled_cells:
            QMessageBox.warning(self, "Nothing to Export", "Draw at least one cell before exporting.")
            return
        suggested = model.name.strip().replace(" ", "_").lower() or "custom_crosshair"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crosshair",
            f"{suggested}.chgrid",
            "Creator Crosshair (*.chgrid)",
        )
        if not path:
            return
        if not path.lower().endswith(".chgrid"):
            path = f"{path}.chgrid"
        self.export_requested.emit(model, path)
        self._set_status(f"Exported '{model.name}' as .chgrid")

    def _build_model(self, validate_name: bool) -> CreatorCrosshair | None:
        name = self._name_input.text().strip()
        if validate_name and not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a crosshair name.")
            return None
        name = name or "Unnamed Crosshair"
        mode = self._mode_combo.currentData()
        if not isinstance(mode, str):
            mode = "draw"
        return CreatorCrosshair(
            name=name,
            grid_size=self._grid.grid_size(),
            creation_mode=mode,
            color_hex=self._color_input.text().strip().upper(),
            filled_cells=sorted(self._grid.cells()),
        )

    def _refresh_preview(self) -> None:
        model = self._build_model(validate_name=False)
        if model is None:
            return
        style = creator_to_overlay_style(model, style_id="preview")
        self._preview_neutral.set_overlay_style(style)
        self._preview_dark.set_overlay_style(style)
        self._preview_light.set_overlay_style(style)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty

    def _confirm_discard_if_dirty(self) -> bool:
        if not self._dirty:
            return True
        result = QMessageBox.question(
            self,
            "Discard Changes?",
            "You have unsaved creator changes. Continue and discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self.status_message.emit(text)
