from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QFileInfo, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..components import InfoChip, PageHeader, SectionCard


@dataclass(frozen=True)
class GameRowModel:
    game_id: str
    title: str
    source: str
    executable_path: str
    icon_path: str
    assigned_style_id: str
    enabled: bool


class GameProfileDialog(QDialog):
    def __init__(self, model: GameRowModel, style_items: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._open_library_requested = False
        self._enable_checkbox = QCheckBox("Auto apply this game profile", self)
        self._style_combo = QComboBox(self)
        self._build_ui(style_items)
        self._wire_signals()

    def _build_ui(self, style_items: list[tuple[str, str]]) -> None:
        self.setWindowTitle(f"Game Profile - {self._model.title}")
        self.setModal(True)
        self.resize(440, 220)

        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self._model.title, self)
        title.setObjectName("CardTitle")
        root.addWidget(title)

        source_line = QLabel(f"Source: {self._model.source.title()}", self)
        source_line.setObjectName("Muted")
        root.addWidget(source_line)

        executable = self._model.executable_path or "Not detected"
        exe_line = QLabel(f"Executable: {executable}", self)
        exe_line.setObjectName("Muted")
        exe_line.setWordWrap(True)
        root.addWidget(exe_line)

        self._enable_checkbox.setChecked(self._model.enabled)
        root.addWidget(self._enable_checkbox)

        self._style_combo.addItem("No Auto Crosshair", userData="")
        for style_id, style_name in style_items:
            self._style_combo.addItem(style_name, userData=style_id)
        target_index = 0
        for index in range(self._style_combo.count()):
            if self._style_combo.itemData(index) == self._model.assigned_style_id:
                target_index = index
                break
        self._style_combo.setCurrentIndex(target_index)
        self._style_combo.setEnabled(self._model.enabled)
        root.addWidget(self._style_combo)

        open_library = QPushButton("Select Crosshair In Library", self)
        open_library.setObjectName("PrimaryButton")
        open_library.clicked.connect(self._on_open_library_clicked)
        root.addWidget(open_library)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._enable_checkbox.toggled.connect(self._style_combo.setEnabled)

    def values(self) -> tuple[str, bool]:
        style_id = str(self._style_combo.currentData() or "")
        enabled = bool(self._enable_checkbox.isChecked() and style_id)
        return style_id, enabled

    @property
    def open_library_requested(self) -> bool:
        return self._open_library_requested

    def _on_open_library_clicked(self) -> None:
        self._open_library_requested = True
        self.accept()


class GameProfileRow(QFrame):
    changed = Signal(str, str, bool)
    open_crosshair_library_requested = Signal()

    def __init__(self, model: GameRowModel, style_items: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model
        self._style_items = style_items
        self._icon = QPushButton(self)
        self._status = QLabel(self)
        self._menu_button = QPushButton("Open Menu", self)
        self._build_ui()
        self._set_icon()
        self._refresh_status_text()

    def _build_ui(self) -> None:
        self.setObjectName("SubtleCard")
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._icon.setFixedSize(42, 42)
        self._icon.setEnabled(False)
        self._icon.setObjectName("GhostButton")
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(self._model.title, self)
        title.setObjectName("CardTitle")
        source = QLabel(f"{self._model.source.title()}  |  {self._exe_label()}", self)
        source.setObjectName("Muted")
        source.setWordWrap(True)
        self._status.setObjectName("Muted")
        self._status.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(source)
        text_col.addWidget(self._status)
        layout.addLayout(text_col, 1)

        self._menu_button.setObjectName("PrimaryButton")
        self._menu_button.clicked.connect(self._open_dialog)
        layout.addWidget(self._menu_button)
        self.setLayout(layout)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_dialog()
            event.accept()
            return
        super().mousePressEvent(event)

    def _exe_label(self) -> str:
        if not self._model.executable_path:
            return "Executable not detected"
        return Path(self._model.executable_path).name

    def _set_icon(self) -> None:
        icon_path = self._model.icon_path or self._model.executable_path
        if icon_path and Path(icon_path).exists():
            provider = QFileIconProvider()
            icon = provider.icon(QFileInfo(icon_path))
            self._icon.setText("")
            self._icon.setIcon(icon)
            self._icon.setIconSize(self._icon.size())
            return

        fallback = QPixmap(26, 26)
        fallback.fill(Qt.GlobalColor.transparent)
        self._icon.setText("G")
        self._icon.setIconSize(fallback.size())

    def _refresh_status_text(self) -> None:
        if not self._model.enabled or not self._model.assigned_style_id:
            self._status.setText("Profile: Off")
            return
        style_name = self._model.assigned_style_id
        for style_id, label in self._style_items:
            if style_id == self._model.assigned_style_id:
                style_name = label
                break
        self._status.setText(f"Profile: On  |  Crosshair: {style_name}")

    def _open_dialog(self) -> None:
        dialog = GameProfileDialog(model=self._model, style_items=self._style_items, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.open_library_requested:
            self.open_crosshair_library_requested.emit()
            return
        style_id, enabled = dialog.values()
        self._model = GameRowModel(
            game_id=self._model.game_id,
            title=self._model.title,
            source=self._model.source,
            executable_path=self._model.executable_path,
            icon_path=self._model.icon_path,
            assigned_style_id=style_id,
            enabled=enabled,
        )
        self._refresh_status_text()
        self.changed.emit(self._model.game_id, style_id, enabled)


class GamesPage(QWidget):
    fullscreen_auto_toggled = Signal(bool)
    game_auto_switch_toggled = Signal(bool)
    game_profile_updated = Signal(str, str, bool)
    import_game_requested = Signal(str)
    rescan_requested = Signal()
    open_crosshair_library_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout()
        self._rows_scroll = QScrollArea(self)
        self._fullscreen_toggle = QCheckBox("Enable only in fullscreen", self)
        self._game_switch_toggle = QCheckBox("Auto-switch by running game", self)
        self._status = QLabel("Waiting for game detection...", self)
        self._style_items: list[tuple[str, str]] = []
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Game Profiles",
                "Click any game to open its menu and set auto profile behavior.",
                eyebrow="Automation",
                parent=self,
            )
        )

        control_card = QFrame(self)
        control_card.setObjectName("HeroCard")
        controls = QVBoxLayout()
        controls.setContentsMargins(18, 18, 18, 18)
        controls.setSpacing(10)
        controls.addWidget(InfoChip("Automatic Runtime Rules", accent=True, parent=self))
        controls.addWidget(self._fullscreen_toggle)
        controls.addWidget(self._game_switch_toggle)
        self._status.setObjectName("Muted")
        self._status.setWordWrap(True)
        controls.addWidget(self._status)

        buttons = QHBoxLayout()
        rescan = QPushButton("Scan Steam + Epic", self)
        rescan.setObjectName("PrimaryButton")
        rescan.clicked.connect(self.rescan_requested.emit)
        import_btn = QPushButton("Import Other Game .exe", self)
        import_btn.clicked.connect(self._on_import_game_clicked)
        buttons.addWidget(rescan)
        buttons.addWidget(import_btn)
        buttons.addStretch(1)
        controls.addLayout(buttons)
        control_card.setLayout(controls)
        root.addWidget(control_card)

        list_card = SectionCard(
            "Detected Library",
            "Click a game row to open its own menu and configure crosshair auto-open settings.",
            parent=self,
        )
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(10)
        self._rows_layout.addStretch(1)
        self._rows_container.setLayout(self._rows_layout)
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_scroll.setWidget(self._rows_container)
        list_card.body.addWidget(self._rows_scroll, 1)
        root.addWidget(list_card, 1)
        self.setLayout(root)

    def _wire_signals(self) -> None:
        self._fullscreen_toggle.toggled.connect(self.fullscreen_auto_toggled.emit)
        self._game_switch_toggle.toggled.connect(self.game_auto_switch_toggled.emit)

    def set_runtime_toggles(self, fullscreen_enabled: bool, game_switch_enabled: bool) -> None:
        self._fullscreen_toggle.blockSignals(True)
        self._game_switch_toggle.blockSignals(True)
        self._fullscreen_toggle.setChecked(fullscreen_enabled)
        self._game_switch_toggle.setChecked(game_switch_enabled)
        self._fullscreen_toggle.blockSignals(False)
        self._game_switch_toggle.blockSignals(False)

    def set_runtime_status(self, text: str) -> None:
        self._status.setText(text)

    def set_games(self, games: list[GameRowModel], style_items: list[tuple[str, str]]) -> None:
        self._style_items = style_items

        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        if not games:
            empty = QLabel("No supported libraries found yet. Use scan or import a game executable.", self)
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self._rows_layout.insertWidget(0, empty)
            return

        for model in games:
            row = GameProfileRow(model=model, style_items=self._style_items, parent=self)
            row.changed.connect(self.game_profile_updated.emit)
            row.open_crosshair_library_requested.connect(self.open_crosshair_library_requested.emit)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)

    def _on_import_game_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Game Executable",
            str(Path.home()),
            "Executable (*.exe)",
        )
        if path:
            self.import_game_requested.emit(path)
