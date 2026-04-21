from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...crosshairs.io import XHAIR_EXTENSION
from ...crosshairs.models import CrosshairDefinition, SettingKind, style_with_updates
from ...overlay_renderer import draw_overlay_style
from ..components import InfoChip, PageHeader, SectionCard


class DetailPreview(QWidget):
    def __init__(self, background: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._background = QColor(background)
        self._definition: CrosshairDefinition | None = None
        self.setMinimumSize(220, 140)

    def set_definition(self, definition: CrosshairDefinition) -> None:
        self._definition = definition
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rounded_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background)
        painter.drawRoundedRect(rounded_rect, 12, 12)
        if self._definition is not None:
            draw_overlay_style(painter, rounded_rect, self._definition.style.scaled(220))


class CrosshairDetailPage(QWidget):
    back_requested = Signal()
    activate_requested = Signal(str)
    live_style_changed = Signal(object)
    save_variant_requested = Signal(object)
    export_requested = Signal(str, str)
    send_to_editor_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._definition: CrosshairDefinition | None = None
        self._draft_name = QLineEdit(self)
        self._description = QLabel("", self)
        self._form_container = QFrame(self)
        self._form_layout = QFormLayout()
        self._preview_dark = DetailPreview("#0D1320", self)
        self._preview_light = DetailPreview("#EEF2F8", self)
        self._status = QLabel("Select a crosshair to edit.", self)
        self._controls: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(self)
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        top_bar = QHBoxLayout()
        back_arrow = QPushButton("Back to Library", self)
        back_arrow.setObjectName("GhostButton")
        back_arrow.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(back_arrow, 0, Qt.AlignmentFlag.AlignLeft)
        top_bar.addStretch(1)
        root.addLayout(top_bar)

        self._header = PageHeader(
            "Crosshair Details",
            "Fine-tune supported settings, preview the result, then activate, export, or send it to the creator.",
            eyebrow="Detail View",
            parent=self,
        )
        root.addWidget(self._header)

        overview = QFrame(self)
        overview.setObjectName("HeroCard")
        overview_layout = QVBoxLayout()
        overview_layout.setContentsMargins(18, 18, 18, 18)
        overview_layout.setSpacing(8)

        chip_row = QHBoxLayout()
        self._family_chip = InfoChip("Family", accent=True, parent=self)
        self._source_chip = InfoChip("Source", parent=self)
        chip_row.addWidget(self._family_chip, 0, Qt.AlignmentFlag.AlignLeft)
        chip_row.addWidget(self._source_chip, 0, Qt.AlignmentFlag.AlignLeft)
        chip_row.addStretch(1)
        overview_layout.addLayout(chip_row)
        overview_layout.addWidget(QLabel("Save Variant Name", self))
        overview_layout.addWidget(self._draft_name)
        self._description.setWordWrap(True)
        self._description.setObjectName("Muted")
        overview_layout.addWidget(self._description)
        overview.setLayout(overview_layout)
        root.addWidget(overview)

        body = QHBoxLayout()
        body.setSpacing(16)

        controls_card = SectionCard("Editable Settings", "Only settings declared for this crosshair are exposed here.", parent=self)
        self._form_layout.setHorizontalSpacing(10)
        self._form_layout.setVerticalSpacing(10)
        self._form_container.setLayout(self._form_layout)
        controls_card.body.addWidget(self._form_container)
        controls_card.body.addStretch(1)
        body.addWidget(controls_card, 3)

        preview_card = SectionCard("Live Preview", "Check the crosshair against both dark and bright backgrounds.", object_name="SubtleCard", parent=self)
        preview_card.body.addWidget(QLabel("Dark Surface", self))
        preview_card.body.addWidget(self._preview_dark)
        preview_card.body.addWidget(QLabel("Light Surface", self))
        preview_card.body.addWidget(self._preview_light)
        body.addWidget(preview_card, 2)

        root.addLayout(body, 1)

        actions_card = SectionCard("Actions", "", parent=self)
        action_row = QHBoxLayout()
        activate = QPushButton("Use This", self)
        send_to_editor = QPushButton("Send to Editor", self)
        export_btn = QPushButton(f"Export {XHAIR_EXTENSION}", self)
        save_variant = QPushButton("Save Variant", self)
        activate.setObjectName("PrimaryButton")
        send_to_editor.setObjectName("GhostButton")
        save_variant.setObjectName("PrimaryButton")
        activate.clicked.connect(self._emit_activate)
        send_to_editor.clicked.connect(self._emit_send_to_editor)
        export_btn.clicked.connect(self._export)
        save_variant.clicked.connect(self._save_variant)
        action_row.addWidget(activate)
        action_row.addWidget(send_to_editor)
        action_row.addWidget(export_btn)
        action_row.addStretch(1)
        action_row.addWidget(save_variant)
        actions_card.body.addLayout(action_row)
        actions_card.body.addWidget(self._status)
        self._status.setObjectName("Muted")
        root.addWidget(actions_card)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def set_definition(self, definition: CrosshairDefinition) -> None:
        self._definition = definition
        self._header.set_title(definition.display_name)
        self._draft_name.setText(definition.display_name)
        self._family_chip.setText(definition.family)
        self._source_chip.setText(definition.source_type.replace("_", " ").title())
        self._description.setText(definition.description or "No description available for this crosshair yet.")
        self._clear_dynamic_form()
        self._build_dynamic_form()
        self._refresh_preview()
        self._set_status("Ready")

    def _clear_dynamic_form(self) -> None:
        while self._form_layout.rowCount() > 0:
            self._form_layout.removeRow(0)
        self._controls.clear()

    def _build_dynamic_form(self) -> None:
        if self._definition is None:
            return
        style = self._definition.style
        if not self._definition.editable_settings:
            empty = QLabel("This style does not expose direct detail controls. Send it to the creator if you want a sketch-style edit flow.", self)
            empty.setWordWrap(True)
            empty.setObjectName("Muted")
            self._form_layout.addRow(empty)
            return

        for spec in self._definition.editable_settings:
            if spec.kind == SettingKind.COLOR:
                field = QWidget(self)
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                entry = QLineEdit(QColor(*style.color_rgba).name().upper(), self)
                button = QPushButton("Pick", self)
                button.clicked.connect(lambda _checked=False, edit=entry: self._pick_color(edit))
                entry.editingFinished.connect(self._on_any_setting_changed)
                row.addWidget(entry)
                row.addWidget(button)
                field.setLayout(row)
                self._controls[spec.key] = entry
                self._form_layout.addRow(spec.label, field)
                continue

            if spec.kind == SettingKind.BOOL:
                checkbox = QCheckBox(self)
                checkbox.setChecked(bool(getattr(style, spec.key)))
                checkbox.toggled.connect(self._on_any_setting_changed)
                self._controls[spec.key] = checkbox
                self._form_layout.addRow(spec.label, checkbox)
                continue

            if spec.kind == SettingKind.INT:
                spin = QSpinBox(self)
                spin.setRange(int(spec.minimum or 0), int(spec.maximum or 255))
                spin.setSingleStep(int(spec.step or 1))
                spin.setValue(style.color_rgba[3] if spec.key == "opacity" else int(getattr(style, spec.key)))
                spin.valueChanged.connect(self._on_any_setting_changed)
                self._controls[spec.key] = spin
                self._form_layout.addRow(spec.label, spin)
                continue

            if spec.kind == SettingKind.FLOAT:
                slider = QSlider(Qt.Orientation.Horizontal, self)
                slider.setRange(int((spec.minimum or -180) * 10), int((spec.maximum or 180) * 10))
                slider.setSingleStep(int((spec.step or 1) * 10))
                slider.setValue(int(float(getattr(style, spec.key)) * 10))
                slider.valueChanged.connect(self._on_any_setting_changed)
                self._controls[spec.key] = slider
                self._form_layout.addRow(spec.label, slider)

    def _pick_color(self, target: QLineEdit) -> None:
        current = QColor(target.text().strip())
        color = QColorDialog.getColor(current if current.isValid() else QColor("#FFFFFF"), self, "Pick Crosshair Color")
        if color.isValid():
            target.setText(color.name().upper())
            self._on_any_setting_changed()

    def _collect_updates(self) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for key, widget in self._controls.items():
            if isinstance(widget, QLineEdit):
                color = QColor(widget.text().strip())
                if not color.isValid():
                    color = QColor("#FFFFFF")
                rgba = color.getRgb()
                updates["color_rgba"] = (
                    rgba[0],
                    rgba[1],
                    rgba[2],
                    self._definition.style.color_rgba[3] if self._definition else 255,
                )
            elif isinstance(widget, QCheckBox):
                updates[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                if key == "opacity":
                    base = updates.get("color_rgba", self._definition.style.color_rgba if self._definition else (255, 255, 255, 255))
                    updates["color_rgba"] = (base[0], base[1], base[2], widget.value())
                else:
                    updates[key] = widget.value()
            elif isinstance(widget, QSlider):
                updates[key] = widget.value() / 10.0
        return updates

    def _on_any_setting_changed(self) -> None:
        if self._definition is None:
            return
        updates = self._collect_updates()
        self._definition = self._definition.with_style(style_with_updates(self._definition.style, updates))
        self._refresh_preview()
        self.live_style_changed.emit(self._definition)
        self._set_status("Live update applied.")

    def _refresh_preview(self) -> None:
        if self._definition is None:
            return
        self._preview_dark.set_definition(self._definition)
        self._preview_light.set_definition(self._definition)

    def _emit_activate(self) -> None:
        if self._definition is None:
            return
        self.activate_requested.emit(self._definition.style_id)
        self._set_status("Crosshair activated.")

    def _emit_send_to_editor(self) -> None:
        if self._definition is None:
            return
        self.send_to_editor_requested.emit(self._definition.style_id)
        self._set_status("Sent to creator.")

    def _save_variant(self) -> None:
        if self._definition is None:
            return
        name = self._draft_name.text().strip() or self._definition.display_name
        new_style = style_with_updates(self._definition.style, {"display_name": name})
        self.save_variant_requested.emit(self._definition.with_style(new_style))
        self._set_status(f"Saved variant '{name}'.")

    def _export(self) -> None:
        if self._definition is None:
            return
        suggested = self._definition.display_name.strip().replace(" ", "_").lower() or "crosshair"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crosshair",
            f"{suggested}{XHAIR_EXTENSION}",
            f"Crosshair Definition (*{XHAIR_EXTENSION})",
        )
        if not path:
            return
        if not path.lower().endswith(XHAIR_EXTENSION):
            path = f"{path}{XHAIR_EXTENSION}"
        self.export_requested.emit(self._definition.style_id, path)
        self._set_status(f"Exported to {path}.")

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
