from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...config import OverlayStyle
from ...overlay_renderer import draw_overlay_style
from ..components import InfoChip, MetricCard, PageHeader, SectionCard


class HomePreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style: OverlayStyle | None = None
        self.setMinimumSize(210, 210)

    def set_style(self, style: OverlayStyle | None) -> None:
        self._style = style
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = self.rect().adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor("#2B3545"), 1))
        painter.setBrush(QColor("#0F1723"))
        painter.drawRoundedRect(outer, 16, 16)

        preview_rect = QRectF(outer.left() + 14, outer.top() + 14, outer.width() - 28, outer.height() - 28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111B29"))
        painter.drawRoundedRect(preview_rect, 14, 14)
        if self._style is not None:
            draw_overlay_style(painter, preview_rect, self._style.scaled(230))


class HomePage(QWidget):
    enable_requested = Signal()
    disable_requested = Signal()
    quit_requested = Signal()
    quick_style_selected = Signal(str)
    choose_crosshair_requested = Signal()

    def __init__(self, style_names: list[tuple[str, str]], current_style_id: str) -> None:
        super().__init__()
        self._style_names = style_names
        self._overlay_enabled = True
        self._current_style_name = "-"
        self._status_chip = InfoChip("Overlay Online", accent=True, parent=self)
        self._selected_style_label = QLabel("-", self)
        self._quick_selector = QComboBox(self)
        self._preview = HomePreview(self)
        self._overlay_toggle_button = QPushButton("Deactivate", self)
        self._choose_button = QPushButton("Choose Crosshair", self)
        self._quit_button = QPushButton("Quit", self)
        self._library_metric = MetricCard("Library Items", "0", self)
        self._theme_metric = MetricCard("Theme", "Adaptive", self)
        self._state_metric = MetricCard("State", "Ready", self)
        self._build_ui()
        self._load_styles(current_style_id)
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "Crosshair Overlay",
                "A cleaner control center for your overlay, library, and creator workflows.",
                eyebrow="Dashboard",
                parent=self,
            )
        )

        hero = QFrame(self)
        hero.setObjectName("HeroCard")
        hero_layout = QGridLayout()
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setHorizontalSpacing(16)
        hero_layout.setVerticalSpacing(16)

        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        title_row = QHBoxLayout()
        title_row.addWidget(self._status_chip, 0, Qt.AlignmentFlag.AlignLeft)
        title_row.addStretch(1)
        left_column.addLayout(title_row)

        headline = QLabel("Your active crosshair is always one click away.", self)
        headline.setObjectName("CardTitle")
        left_column.addWidget(headline)

        self._selected_style_label.setWordWrap(True)
        left_column.addWidget(self._selected_style_label)

        action_row = QHBoxLayout()
        self._choose_button.setObjectName("PrimaryButton")
        self._overlay_toggle_button.setObjectName("NeutralButton")
        self._quit_button.setObjectName("GhostButton")
        action_row.addWidget(self._choose_button)
        action_row.addWidget(self._overlay_toggle_button)
        action_row.addWidget(self._quit_button)
        action_row.addStretch(1)
        left_column.addLayout(action_row)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        metrics.addWidget(self._library_metric)
        metrics.addWidget(self._theme_metric)
        metrics.addWidget(self._state_metric)
        left_column.addLayout(metrics)

        left_wrap = QWidget(self)
        left_wrap.setLayout(left_column)
        hero_layout.addWidget(left_wrap, 0, 0)
        hero_layout.addWidget(self._preview, 0, 1)
        hero.setLayout(hero_layout)
        root.addWidget(hero)

        content = QHBoxLayout()
        content.setSpacing(16)

        quick_picker = SectionCard(
            "Quick Selector",
            "Change the active overlay style instantly or jump into the library for deeper browsing.",
            parent=self,
        )
        quick_picker.body.addWidget(self._quick_selector)
        picker_row = QHBoxLayout()
        apply_button = QPushButton("Use Selected", self)
        apply_button.setObjectName("PrimaryButton")
        apply_button.clicked.connect(self._emit_quick_selection)
        browse_button = QPushButton("Open Library", self)
        browse_button.setObjectName("GhostButton")
        browse_button.clicked.connect(self.choose_crosshair_requested.emit)
        picker_row.addWidget(apply_button)
        picker_row.addWidget(browse_button)
        quick_picker.body.addLayout(picker_row)
        content.addWidget(quick_picker, 3)

        shortcuts = SectionCard(
            "Quick Access",
            "Move between the library, creator, and settings without hunting through utilitarian panels.",
            object_name="SubtleCard",
            parent=self,
        )
        shortcuts.body.addWidget(QLabel("Use the sidebar to open Crosshairs, Creator, Games, or Settings.", self))
        shortcuts.body.addWidget(QLabel("Home is now the app dashboard rather than just a temporary control page.", self))
        content.addWidget(shortcuts, 2)

        root.addLayout(content)
        root.addStretch(1)
        self.setLayout(root)

    def _load_styles(self, current_style_id: str) -> None:
        self._quick_selector.blockSignals(True)
        self._quick_selector.clear()
        selected_index = 0
        for idx, (style_id, style_name) in enumerate(self._style_names):
            self._quick_selector.addItem(style_name, userData=style_id)
            if style_id == current_style_id:
                selected_index = idx
        self._quick_selector.setCurrentIndex(selected_index)
        self._quick_selector.blockSignals(False)
        self.set_selected_style_name(self._quick_selector.currentText())
        self._update_metrics()

    def refresh_styles(self, style_names: list[tuple[str, str]], selected_style_id: str) -> None:
        self._style_names = style_names
        self._load_styles(current_style_id=selected_style_id)

    def _wire_signals(self) -> None:
        self._overlay_toggle_button.clicked.connect(self._on_overlay_toggle_clicked)
        self._quit_button.clicked.connect(self.quit_requested.emit)
        self._choose_button.clicked.connect(self.choose_crosshair_requested.emit)

    def set_overlay_status(self, enabled: bool) -> None:
        self._overlay_enabled = enabled
        self._status_chip.setText("Overlay Online" if enabled else "Overlay Paused")
        self._status_chip.setObjectName("AccentChip" if enabled else "InfoChip")
        self._status_chip.style().polish(self._status_chip)
        if enabled:
            self._overlay_toggle_button.setText("Deactivate")
            self._overlay_toggle_button.setObjectName("NeutralButton")
        else:
            self._overlay_toggle_button.setText("Activate")
            self._overlay_toggle_button.setObjectName("PrimaryButton")
        self._overlay_toggle_button.style().unpolish(self._overlay_toggle_button)
        self._overlay_toggle_button.style().polish(self._overlay_toggle_button)
        self._update_metrics()

    def set_selected_style(self, style_id: str) -> None:
        for index in range(self._quick_selector.count()):
            if self._quick_selector.itemData(index) == style_id:
                self._quick_selector.setCurrentIndex(index)
                return

    def set_selected_style_name(self, style_name: str) -> None:
        self._current_style_name = style_name or "-"
        self._selected_style_label.setText(f"Active Crosshair: {self._current_style_name}")

    def set_active_style_preview(self, style: OverlayStyle) -> None:
        self._preview.set_style(style)

    def _emit_quick_selection(self) -> None:
        style_id = self._quick_selector.currentData()
        if isinstance(style_id, str):
            self.quick_style_selected.emit(style_id)

    def _on_overlay_toggle_clicked(self) -> None:
        if self._overlay_enabled:
            self.disable_requested.emit()
        else:
            self.enable_requested.emit()

    def _update_metrics(self) -> None:
        for card, text in (
            (self._library_metric, str(len(self._style_names))),
            (self._theme_metric, "Adaptive"),
            (self._state_metric, "Live" if self._overlay_enabled else "Idle"),
        ):
            values = card.findChildren(QLabel, "MetricValue")
            if values:
                values[0].setText(text)
