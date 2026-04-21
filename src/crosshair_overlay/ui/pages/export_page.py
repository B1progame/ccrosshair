from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...crosshairs.models import CrosshairDefinition
from ...overlay_renderer import draw_overlay_style
from ..components import PageHeader, SectionCard


class ExportPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._definition: CrosshairDefinition | None = None
        self._scale_percent = 100
        self._surface = QColor("#0E1624")
        self.setMinimumSize(260, 220)

    def set_definition(self, definition: CrosshairDefinition | None) -> None:
        self._definition = definition
        self.update()

    def set_scale_percent(self, value: int) -> None:
        self._scale_percent = max(40, min(250, int(value)))
        self.update()

    def set_surface(self, color_hex: str) -> None:
        color = QColor(color_hex)
        if color.isValid():
            self._surface = color
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._surface)
        painter.drawRoundedRect(outer, 12, 12)
        if self._definition is None:
            painter.setPen(QColor("#B3C1D6"))
            painter.drawText(outer, Qt.AlignmentFlag.AlignCenter, "No style selected")
            return
        draw_overlay_style(painter, QRectF(outer), self._definition.style.scaled(self._scale_percent))


class ExportPage(QWidget):
    export_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._definition: CrosshairDefinition | None = None
        self._format_combo = QComboBox(self)
        self._surface_combo = QComboBox(self)
        self._size_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._size_label = QLabel("100%", self)
        self._outline_combo = QComboBox(self)
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._opacity_label = QLabel("100%", self)
        self._preview = ExportPreview(self)
        self._status = QLabel("Select a crosshair from the library to export.", self)
        self._export_button = QPushButton("Export Current Crosshair", self)
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Export",
                "Dedicated export workspace with controllable preview settings.",
                eyebrow="Output",
                parent=self,
            )
        )

        controls = SectionCard(
            "Export Options",
            "Format and preview options are centralized here instead of hidden in context-specific views.",
            parent=self,
        )
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Format", self))
        self._format_combo.addItem(".xhair (single style)", userData=".xhair")
        row1.addWidget(self._format_combo)
        row1.addWidget(QLabel("Surface", self))
        self._surface_combo.addItem("Dark", userData="#0E1624")
        self._surface_combo.addItem("Mid", userData="#1B2638")
        self._surface_combo.addItem("Light", userData="#E9EEF8")
        row1.addWidget(self._surface_combo)
        row1.addWidget(QLabel("Outline", self))
        self._outline_combo.addItems(["Keep", "Force On", "Force Off"])
        row1.addWidget(self._outline_combo)
        controls.body.addLayout(row1)

        row2 = QHBoxLayout()
        self._size_slider.setRange(50, 200)
        self._size_slider.setValue(100)
        row2.addWidget(QLabel("Size", self))
        row2.addWidget(self._size_slider, 1)
        row2.addWidget(self._size_label)
        controls.body.addLayout(row2)

        row3 = QHBoxLayout()
        self._opacity_slider.setRange(20, 100)
        self._opacity_slider.setValue(100)
        row3.addWidget(QLabel("Opacity", self))
        row3.addWidget(self._opacity_slider, 1)
        row3.addWidget(self._opacity_label)
        controls.body.addLayout(row3)

        root.addWidget(controls)

        preview_card = QFrame(self)
        preview_card.setObjectName("SubtleCard")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.addWidget(QLabel("Live Export Preview", self))
        preview_layout.addWidget(self._preview, 1)
        preview_card.setLayout(preview_layout)
        root.addWidget(preview_card, 1)

        actions = QHBoxLayout()
        self._export_button.setObjectName("PrimaryButton")
        actions.addWidget(self._export_button)
        actions.addStretch(1)
        root.addLayout(actions)
        self._status.setObjectName("Muted")
        root.addWidget(self._status)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._surface_combo.currentIndexChanged.connect(self._refresh_preview)
        self._size_slider.valueChanged.connect(self._refresh_preview)
        self._opacity_slider.valueChanged.connect(self._refresh_preview)
        self._outline_combo.currentIndexChanged.connect(self._refresh_preview)
        self._export_button.clicked.connect(self._on_export_clicked)

    def set_definition(self, definition: CrosshairDefinition | None) -> None:
        self._definition = definition
        if definition is None:
            self._status.setText("Select a crosshair from the library to export.")
        else:
            self._status.setText(f"Ready to export: {definition.display_name}")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self._size_label.setText(f"{self._size_slider.value()}%")
        self._opacity_label.setText(f"{self._opacity_slider.value()}%")
        self._preview.set_scale_percent(self._size_slider.value())
        self._preview.set_surface(str(self._surface_combo.currentData() or "#0E1624"))
        if self._definition is None:
            self._preview.set_definition(None)
            return
        definition = self._definition
        if self._outline_combo.currentIndex() == 1:
            definition = definition.with_style(replace(definition.style, outline_enabled=True))
        elif self._outline_combo.currentIndex() == 2:
            definition = definition.with_style(replace(definition.style, outline_enabled=False))
        alpha = int(round((self._opacity_slider.value() / 100.0) * 255))
        rgba = definition.style.color_rgba
        style = replace(definition.style, color_rgba=(rgba[0], rgba[1], rgba[2], alpha))
        self._preview.set_definition(definition.with_style(style))

    def _on_export_clicked(self) -> None:
        if self._definition is None:
            self._status.setText("Select a crosshair first.")
            return
        suffix = str(self._format_combo.currentData() or ".xhair")
        base = self._definition.display_name.strip().replace(" ", "_").lower() or "crosshair"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crosshair",
            str(Path.home() / f"{base}{suffix}"),
            f"Crosshair (*{suffix})",
        )
        if not destination:
            return
        if not destination.lower().endswith(suffix):
            destination = f"{destination}{suffix}"
        self.export_requested.emit(destination)
        self._status.setText(f"Exported to {destination}")
