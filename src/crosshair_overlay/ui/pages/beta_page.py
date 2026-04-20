from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...app_settings import BetaZoomSettings
from ..components import InfoChip, PageHeader, SectionCard


class BetaPreviewLabel(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(340, 220)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("SubtleCard")
        self.setText("Live preview will appear here.")

    def set_preview(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self.setText("Live preview will appear here.")
            self.setPixmap(QPixmap())
            return
        self.setText("")
        self.setPixmap(
            pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        pixmap = self.pixmap()
        if pixmap is not None and not pixmap.isNull():
            self.set_preview(pixmap)
        super().resizeEvent(event)


class BetaPage(QWidget):
    settings_changed = Signal(object)
    MODE_ON_CROSSHAIR = "crosshair"
    MODE_MONITOR = "monitor"

    def __init__(self) -> None:
        super().__init__()
        self._settings = BetaZoomSettings()
        self._monitor_choices: list[tuple[str, str]] = [("same_as_game", "Same as Game Monitor")]
        self._live_enabled_checkbox = QCheckBox("Always show live zoom", self)
        self._enabled_checkbox = QCheckBox("Enable zoom hotkey", self)
        self._hotkey_input = QKeySequenceEdit(self)
        self._clear_hotkey_button = QPushButton("Clear Hotkey", self)
        self._mode_combo = QComboBox(self)
        self._monitor_combo = QComboBox(self)
        self._position_x_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._position_y_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._position_x_label = QLabel(self)
        self._position_y_label = QLabel(self)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._zoom_label = QLabel(self)
        self._animation_checkbox = QCheckBox("Animated zoom-in", self)
        self._animation_duration_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._animation_duration_label = QLabel(self)
        self._preview = BetaPreviewLabel(self)
        self._build_ui()
        self._wire_signals()
        self.set_settings(self._settings)

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Zoom",
                "Choose whether zoom follows your crosshair directly or stays live in a separate monitor window.",
                eyebrow="Live Magnifier",
                parent=self,
            )
        )

        hero = QFrame(self)
        hero.setObjectName("HeroCard")
        hero_layout = QGridLayout()
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setHorizontalSpacing(14)
        hero_layout.setVerticalSpacing(12)

        hero_layout.addWidget(InfoChip("Live Preview", accent=True, parent=self), 0, 0, 1, 2)
        hero_layout.addWidget(self._live_enabled_checkbox, 1, 0)
        hero_layout.addWidget(self._enabled_checkbox, 1, 1)
        hero_layout.addWidget(QLabel("Zoom Mode", self), 2, 0)
        self._mode_combo.addItem("On Crosshair", userData=self.MODE_ON_CROSSHAIR)
        self._mode_combo.addItem("Monitor Window", userData=self.MODE_MONITOR)
        hero_layout.addWidget(self._mode_combo, 3, 0)
        hero_layout.addWidget(QLabel("Hotkey", self), 4, 0)
        if hasattr(self._hotkey_input, "setMaximumSequenceLength"):
            self._hotkey_input.setMaximumSequenceLength(1)
        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(8)
        hotkey_row.addWidget(self._hotkey_input, 1)
        hotkey_row.addWidget(self._clear_hotkey_button, 0)
        hotkey_wrap = QWidget(self)
        hotkey_wrap.setLayout(hotkey_row)
        hero_layout.addWidget(hotkey_wrap, 5, 0)
        hero_layout.addWidget(QLabel("Display Monitor", self), 4, 1)
        hero_layout.addWidget(self._monitor_combo, 5, 1)
        hero_layout.addWidget(self._preview, 6, 0, 1, 2)
        hero.setLayout(hero_layout)
        root.addWidget(hero)

        controls = QHBoxLayout()
        controls.setSpacing(16)

        placement = SectionCard(
            "Placement",
            "For monitor mode, choose where the live zoom window should appear. In crosshair mode, this section is disabled.",
            parent=self,
        )
        self._position_x_slider.setRange(0, 100)
        self._position_y_slider.setRange(0, 100)
        placement.body.addWidget(QLabel("Horizontal Position", self))
        placement.body.addWidget(self._position_x_slider)
        placement.body.addWidget(self._position_x_label)
        placement.body.addWidget(QLabel("Vertical Position", self))
        placement.body.addWidget(self._position_y_slider)
        placement.body.addWidget(self._position_y_label)
        controls.addWidget(placement, 1)

        zoom = SectionCard(
            "Zoom",
            "Use live zoom for an always-visible magnifier, or keep hotkey zoom enabled for a quick temporary popup.",
            object_name="SubtleCard",
            parent=self,
        )
        self._zoom_slider.setRange(200, 10000)
        self._zoom_slider.setSingleStep(50)
        self._animation_duration_slider.setRange(0, 1500)
        self._animation_duration_slider.setSingleStep(10)
        zoom.body.addWidget(QLabel("Zoom Amount", self))
        zoom.body.addWidget(self._zoom_slider)
        zoom.body.addWidget(self._zoom_label)
        zoom.body.addWidget(self._animation_checkbox)
        zoom.body.addWidget(self._animation_duration_slider)
        zoom.body.addWidget(self._animation_duration_label)
        controls.addWidget(zoom, 1)

        root.addLayout(controls)
        root.addStretch(1)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._live_enabled_checkbox.toggled.connect(self._emit_settings)
        self._enabled_checkbox.toggled.connect(self._emit_settings)
        self._hotkey_input.keySequenceChanged.connect(self._emit_settings)
        self._clear_hotkey_button.clicked.connect(self._clear_hotkey)
        self._mode_combo.currentIndexChanged.connect(self._emit_settings)
        self._monitor_combo.currentIndexChanged.connect(self._emit_settings)
        self._position_x_slider.valueChanged.connect(self._emit_settings)
        self._position_y_slider.valueChanged.connect(self._emit_settings)
        self._zoom_slider.valueChanged.connect(self._emit_settings)
        self._animation_checkbox.toggled.connect(self._emit_settings)
        self._animation_duration_slider.valueChanged.connect(self._emit_settings)

    def set_monitor_choices(self, choices: list[tuple[str, str]]) -> None:
        self._monitor_choices = choices or [("same_as_game", "Same as Game Monitor")]
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.clear()
        for monitor_id, label in self._monitor_choices:
            self._monitor_combo.addItem(label, userData=monitor_id)
        self._monitor_combo.blockSignals(False)
        self.set_settings(self._settings)

    def set_settings(self, settings: BetaZoomSettings) -> None:
        self._settings = settings
        self._live_enabled_checkbox.blockSignals(True)
        self._live_enabled_checkbox.setChecked(settings.live_enabled)
        self._live_enabled_checkbox.blockSignals(False)

        self._enabled_checkbox.blockSignals(True)
        self._enabled_checkbox.setChecked(settings.zoom_enabled)
        self._enabled_checkbox.blockSignals(False)

        self._set_hotkey_text(settings.hotkey_sequence)

        mode_value = settings.display_mode if settings.display_mode in {self.MODE_ON_CROSSHAIR, self.MODE_MONITOR} else self.MODE_MONITOR
        mode_index = 0
        for index in range(self._mode_combo.count()):
            if self._mode_combo.itemData(index) == mode_value:
                mode_index = index
                break
        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(mode_index)
        self._mode_combo.blockSignals(False)

        monitor_index = 0
        for index in range(self._monitor_combo.count()):
            if self._monitor_combo.itemData(index) == settings.target_monitor_id:
                monitor_index = index
                break
        self._monitor_combo.blockSignals(True)
        self._monitor_combo.setCurrentIndex(monitor_index)
        self._monitor_combo.blockSignals(False)

        self._position_x_slider.blockSignals(True)
        self._position_y_slider.blockSignals(True)
        self._zoom_slider.blockSignals(True)
        self._animation_checkbox.blockSignals(True)
        self._animation_duration_slider.blockSignals(True)

        self._position_x_slider.setValue(settings.position_x_percent)
        self._position_y_slider.setValue(settings.position_y_percent)
        self._zoom_slider.setValue(settings.zoom_percent)
        self._animation_checkbox.setChecked(settings.animation_enabled)
        self._animation_duration_slider.setValue(settings.animation_duration_ms)

        self._position_x_slider.blockSignals(False)
        self._position_y_slider.blockSignals(False)
        self._zoom_slider.blockSignals(False)
        self._animation_checkbox.blockSignals(False)
        self._animation_duration_slider.blockSignals(False)

        self._position_x_label.setText(f"{settings.position_x_percent}%")
        self._position_y_label.setText(f"{settings.position_y_percent}%")
        self._zoom_label.setText(f"{settings.zoom_percent}%")
        self._animation_duration_label.setText(f"{settings.animation_duration_ms} ms")
        self._animation_duration_slider.setEnabled(settings.animation_enabled)
        self._refresh_visibility_state()

    def set_preview_pixmap(self, pixmap: QPixmap | None) -> None:
        self._preview.set_preview(pixmap)

    def _emit_settings(self, *_args) -> None:
        sequence = self._normalized_hotkey_text(self._hotkey_input.keySequence())
        current_display = self._hotkey_input.keySequence().toString(QKeySequence.SequenceFormat.PortableText).strip()
        if current_display != sequence:
            self._set_hotkey_text(sequence)
        display_mode = str(self._mode_combo.currentData() or self.MODE_MONITOR)
        target_monitor_id = str(self._monitor_combo.currentData() or "same_as_game")
        updated = replace(
            self._settings,
            live_enabled=self._live_enabled_checkbox.isChecked(),
            zoom_enabled=self._enabled_checkbox.isChecked(),
            hotkey_sequence=sequence,
            display_mode=display_mode,
            target_monitor_id=target_monitor_id,
            position_x_percent=self._position_x_slider.value(),
            position_y_percent=self._position_y_slider.value(),
            zoom_percent=self._zoom_slider.value(),
            animation_enabled=self._animation_checkbox.isChecked(),
            animation_duration_ms=self._animation_duration_slider.value(),
        )
        self._position_x_label.setText(f"{updated.position_x_percent}%")
        self._position_y_label.setText(f"{updated.position_y_percent}%")
        self._zoom_label.setText(f"{updated.zoom_percent}%")
        self._animation_duration_label.setText(f"{updated.animation_duration_ms} ms")
        self._animation_duration_slider.setEnabled(updated.animation_enabled)
        self._settings = updated
        self._refresh_visibility_state()
        self.settings_changed.emit(updated)

    def _clear_hotkey(self) -> None:
        self._set_hotkey_text("")
        self._emit_settings()

    def _set_hotkey_text(self, sequence: str) -> None:
        normalized = self._normalized_hotkey_text(QKeySequence(sequence))
        self._hotkey_input.blockSignals(True)
        self._hotkey_input.setKeySequence(QKeySequence(normalized) if normalized else QKeySequence())
        self._hotkey_input.blockSignals(False)

    def _normalized_hotkey_text(self, key_sequence: QKeySequence) -> str:
        for index in range(key_sequence.count()):
            combination = key_sequence[index]
            single = QKeySequence(combination)
            text = single.toString(QKeySequence.SequenceFormat.PortableText).strip()
            if text:
                return text
        return ""

    def _refresh_visibility_state(self) -> None:
        use_monitor_controls = self._settings.display_mode == self.MODE_MONITOR
        self._monitor_combo.setEnabled(use_monitor_controls)
        self._position_x_slider.setEnabled(use_monitor_controls)
        self._position_y_slider.setEnabled(use_monitor_controls)
        self._position_x_label.setEnabled(use_monitor_controls)
        self._position_y_label.setEnabled(use_monitor_controls)
