from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..components import InfoChip, PageHeader, SectionCard


class SettingsPage(QWidget):
    accent_color_changed = Signal(str)
    global_size_changed = Signal(int)
    storage_path_changed = Signal(str)
    beta_features_changed = Signal(bool)
    auto_update_on_startup_changed = Signal(bool)
    run_on_startup_tray_changed = Signal(bool)
    reset_requested = Signal()
    check_updates_requested = Signal()

    def __init__(
        self,
        theme_mode: str,
        accent_color: str,
        global_size_percent: int,
        storage_path: str,
        beta_features_enabled: bool,
        auto_update_on_startup: bool = False,
        run_on_startup_tray: bool = False,
    ) -> None:
        super().__init__()
        self._accent_input = QLineEdit(self)
        self._pick_color_button = QPushButton("Choose Color", self)
        self._accent_swatch = QLabel(self)
        self._accent_error = QLabel(self)
        self._accent_error.setObjectName("ValidationMessage")
        self._accent_error.setAccessibleName("Accent color validation message")
        self._accent_error.hide()
        self._last_valid_accent = "#A923E2"
        self._global_size_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._global_size_label = QLabel(self)
        self._storage_path_input = QLineEdit(storage_path, self)
        self._browse_storage_button = QPushButton("Browse", self)
        self._beta_checkbox = QCheckBox("Show Zoom Page in Sidebar", self)
        self._auto_update_checkbox = QCheckBox("Auto check/update prompt on startup", self)
        self._autostart_tray_checkbox = QCheckBox("Run on Windows startup (tray only)", self)
        self._reset_button = QPushButton("Reset App Settings", self)
        self._check_update_button = QPushButton("Check for New Version", self)
        self._build_ui()
        self._apply_initial_values(
            accent_color,
            global_size_percent,
            storage_path,
            beta_features_enabled,
            auto_update_on_startup,
            run_on_startup_tray,
        )
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Settings",
                "Manage the shared theme, storage layout, and global overlay defaults from one place.",
                eyebrow="Appearance & Storage",
                parent=self,
            )
        )

        appearance = QFrame(self)
        appearance.setObjectName("HeroCard")
        appearance_layout = QGridLayout()
        appearance_layout.setContentsMargins(20, 20, 20, 20)
        appearance_layout.setHorizontalSpacing(12)
        appearance_layout.setVerticalSpacing(12)

        appearance_layout.addWidget(QLabel("Accent Color", self), 0, 0)
        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        self._accent_swatch.setFixedSize(28, 28)
        accent_row.addWidget(self._accent_swatch)
        accent_row.addWidget(self._accent_input)
        accent_row.addWidget(self._pick_color_button)
        accent_wrap = QWidget(self)
        accent_wrap.setLayout(accent_row)
        appearance_layout.addWidget(accent_wrap, 1, 0, 1, 2)
        appearance_layout.addWidget(self._accent_error, 2, 0, 1, 2)
        appearance_layout.addWidget(QLabel("Global Crosshair Size", self), 3, 0, 1, 2)
        size_row = QHBoxLayout()
        self._global_size_slider.setRange(50, 200)
        size_row.addWidget(self._global_size_slider)
        size_row.addWidget(self._global_size_label)
        size_wrap = QWidget(self)
        size_wrap.setLayout(size_row)
        appearance_layout.addWidget(size_wrap, 4, 0, 1, 2)
        appearance.setLayout(appearance_layout)
        root.addWidget(appearance)

        lower = QHBoxLayout()
        lower.setSpacing(16)

        storage = SectionCard(
            "Storage",
            "Imports, creator files, and custom variants are grouped under structured folders inside the library root.",
            parent=self,
        )
        storage.body.addWidget(InfoChip("Organized Library Root", accent=True, parent=self))
        self._storage_path_input.setReadOnly(True)
        storage_row = QHBoxLayout()
        storage_row.addWidget(self._storage_path_input, 1)
        storage_row.addWidget(self._browse_storage_button)
        storage.body.addLayout(storage_row)
        storage.body.addWidget(QLabel("Imported packs now create their own folders automatically.", self))
        lower.addWidget(storage, 3)

        maintenance = SectionCard(
            "Maintenance",
            "Keep the app feeling intentional with clean update and reset actions.",
            object_name="SubtleCard",
            parent=self,
        )
        self._check_update_button.setObjectName("GhostButton")
        self._reset_button.setObjectName("DangerButton")
        maintenance.body.addWidget(self._beta_checkbox)
        maintenance.body.addWidget(self._auto_update_checkbox)
        maintenance.body.addWidget(self._autostart_tray_checkbox)
        maintenance.body.addWidget(self._check_update_button)
        maintenance.body.addWidget(self._reset_button)
        maintenance.body.addStretch(1)
        lower.addWidget(maintenance, 2)

        root.addLayout(lower)
        root.addStretch(1)
        self.setLayout(root)

    def _apply_initial_values(
        self,
        accent_color: str,
        global_size: int,
        storage_path: str,
        beta_features_enabled: bool,
        auto_update_on_startup: bool,
        run_on_startup_tray: bool,
    ) -> None:
        color = QColor(accent_color)
        self._last_valid_accent = color.name().upper() if color.isValid() else "#A923E2"
        self._accent_input.setText(self._last_valid_accent)
        self._update_accent_swatch(self._last_valid_accent)
        self._global_size_slider.setValue(max(50, min(200, global_size)))
        self._global_size_label.setText(f"{self._global_size_slider.value()}%")
        self._storage_path_input.setText(storage_path)
        self._beta_checkbox.setChecked(beta_features_enabled)
        self._auto_update_checkbox.setChecked(auto_update_on_startup)
        self._autostart_tray_checkbox.setChecked(run_on_startup_tray)

    def _wire_signals(self) -> None:
        self._accent_input.editingFinished.connect(self._on_accent_text_changed)
        self._pick_color_button.clicked.connect(self._on_pick_color)
        self._global_size_slider.valueChanged.connect(self._on_global_size_changed)
        self._browse_storage_button.clicked.connect(self._on_browse_storage)
        self._beta_checkbox.toggled.connect(self.beta_features_changed.emit)
        self._auto_update_checkbox.toggled.connect(self.auto_update_on_startup_changed.emit)
        self._autostart_tray_checkbox.toggled.connect(self.run_on_startup_tray_changed.emit)
        self._reset_button.clicked.connect(self.reset_requested.emit)
        self._check_update_button.clicked.connect(self.check_updates_requested.emit)

    def set_storage_path(self, path: str) -> None:
        self._storage_path_input.setText(path)

    def set_theme(self, theme_mode: str, accent_color: str) -> None:
        del theme_mode
        self._accent_input.setText(accent_color.upper())
        self._update_accent_swatch(accent_color.upper())

    def set_global_size(self, value: int) -> None:
        self._global_size_slider.blockSignals(True)
        self._global_size_slider.setValue(value)
        self._global_size_slider.blockSignals(False)
        self._global_size_label.setText(f"{self._global_size_slider.value()}%")

    def set_beta_features_enabled(self, enabled: bool) -> None:
        self._beta_checkbox.blockSignals(True)
        self._beta_checkbox.setChecked(enabled)
        self._beta_checkbox.blockSignals(False)

    def set_startup_preferences(self, auto_update_on_startup: bool, run_on_startup_tray: bool) -> None:
        self._auto_update_checkbox.blockSignals(True)
        self._autostart_tray_checkbox.blockSignals(True)
        self._auto_update_checkbox.setChecked(bool(auto_update_on_startup))
        self._autostart_tray_checkbox.setChecked(bool(run_on_startup_tray))
        self._auto_update_checkbox.blockSignals(False)
        self._autostart_tray_checkbox.blockSignals(False)

    def _update_accent_swatch(self, color_hex: str) -> None:
        self._accent_swatch.setStyleSheet(
            f"background: {color_hex}; border: 1px solid rgba(255,255,255,0.18); border-radius: 10px;"
        )

    def _on_accent_text_changed(self) -> None:
        raw = self._accent_input.text().strip()
        color = QColor(raw)
        if not color.isValid():
            self._accent_error.setText("Enter a valid color, such as #67D4AE.")
            self._accent_error.show()
            self._accent_input.setProperty("invalid", True)
            self._accent_input.style().unpolish(self._accent_input)
            self._accent_input.style().polish(self._accent_input)
            return
        normalized = color.name().upper()
        self._last_valid_accent = normalized
        self._accent_input.setText(normalized)
        self._accent_error.hide()
        self._accent_input.setProperty("invalid", False)
        self._accent_input.style().unpolish(self._accent_input)
        self._accent_input.style().polish(self._accent_input)
        self._update_accent_swatch(normalized)
        self.accent_color_changed.emit(normalized)

    def _on_pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._last_valid_accent), self, "Pick Accent Color")
        if color.isValid():
            normalized = color.name().upper()
            self._accent_input.setText(normalized)
            self._last_valid_accent = normalized
            self._accent_error.hide()
            self._accent_input.setProperty("invalid", False)
            self._update_accent_swatch(normalized)
            self.accent_color_changed.emit(normalized)

    def _on_global_size_changed(self, value: int) -> None:
        self._global_size_label.setText(f"{value}%")
        self.global_size_changed.emit(value)

    def _on_browse_storage(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Crosshair Storage Folder", self._storage_path_input.text())
        if path:
            self._storage_path_input.setText(path)
            self.storage_path_changed.emit(path)
