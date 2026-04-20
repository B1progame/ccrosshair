from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class NavItem:
    page_id: str
    label: str
    icon_key: str


def _build_nav_icon(icon_key: str, color_hex: str = "#8EA9CC") -> QIcon:
    size = 20
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor(color_hex)
    pen = QPen(color, 1.9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if icon_key == "home":
        painter.drawLine(4, 10, 10, 4)
        painter.drawLine(10, 4, 16, 10)
        painter.drawRect(QRectF(5.5, 9.5, 9, 7))
    elif icon_key == "crosshairs":
        cell = 4
        gap = 1.5
        start = 3.5
        for y in range(2):
            for x in range(2):
                painter.drawRect(QRectF(start + (x * (cell + gap)), start + (y * (cell + gap)), cell, cell))
    elif icon_key == "creator":
        painter.drawLine(4, 15, 14, 5)
        painter.drawLine(14, 5, 16, 7)
        painter.drawLine(5, 14, 7, 16)
        painter.drawLine(4, 15, 7, 16)
    elif icon_key == "games":
        path = QPainterPath()
        path.moveTo(QPointF(6, 5))
        path.lineTo(QPointF(15, 10))
        path.lineTo(QPointF(6, 15))
        path.closeSubpath()
        painter.drawPath(path)
    elif icon_key == "settings":
        painter.drawEllipse(QRectF(7, 7, 6, 6))
        center = QPointF(10, 10)
        spokes = (
            QPointF(10, 3),
            QPointF(10, 17),
            QPointF(3, 10),
            QPointF(17, 10),
            QPointF(5.2, 5.2),
            QPointF(14.8, 14.8),
            QPointF(14.8, 5.2),
            QPointF(5.2, 14.8),
        )
        for point in spokes:
            painter.drawLine(center, point)
    elif icon_key == "zoom":
        painter.drawEllipse(QRectF(4.5, 4.5, 8.5, 8.5))
        painter.drawLine(12.5, 12.5, 16.5, 16.5)
    else:
        painter.drawRect(QRectF(5, 5, 10, 10))

    painter.end()
    return QIcon(pixmap)


class NavButton(QPushButton):
    def __init__(self, item: NavItem, parent: QWidget | None = None) -> None:
        super().__init__(item.label, parent)
        self._item = item
        self._expanded_text = item.label
        self._collapsed = False
        self.setCheckable(True)
        self.setToolTip(item.label)
        self.setIcon(_build_nav_icon(item.icon_key))
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("SidebarNavButton")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(38)
        self._apply_alignment_style()

    @property
    def page_id(self) -> str:
        return self._item.page_id

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.setText("" if collapsed else self._expanded_text)
        self.setMinimumWidth(34 if collapsed else 140)
        self._apply_alignment_style()

    def _apply_alignment_style(self) -> None:
        if self._collapsed:
            self.setStyleSheet("text-align: center; padding: 7px 0px;")
        else:
            self.setStyleSheet("text-align: left; padding: 7px 10px;")


class ChevronButton(QAbstractButton):
    toggled_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 180.0
        self._animation = QPropertyAnimation(self, b"angle", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Collapse / Expand")
        self.setFixedSize(28, 28)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggled_requested.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)

        pen = QPen(self.palette().color(self.foregroundRole()), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        path = QPainterPath()
        path.moveTo(-5, -6)
        path.lineTo(2, 0)
        path.lineTo(-5, 6)
        painter.drawPath(path)

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float) -> None:
        self._angle = value
        self.update()

    angle = Property(float, get_angle, set_angle)

    def animate_to_collapsed(self, collapsed: bool) -> None:
        target = 0.0 if collapsed else 180.0
        self._animation.stop()
        self._animation.setStartValue(self._angle)
        self._animation.setEndValue(target)
        self._animation.start()


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    collapse_toggled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self._collapsed = False
        self._buttons: list[NavButton] = []
        self._settings_button: NavButton | None = None
        self._beta_button: NavButton | None = None
        self._arrow_button = ChevronButton(self)
        self._brand_frame: QFrame | None = None
        self._brand_title: QLabel | None = None
        self._brand_subtitle: QLabel | None = None
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        brand = QFrame(self)
        brand.setObjectName("SubtleCard")
        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(12, 12, 12, 12)
        brand_layout.setSpacing(4)
        self._brand_title = QLabel("Crosshair", brand)
        self._brand_title.setObjectName("CardTitle")
        self._brand_subtitle = QLabel("Overlay Studio", brand)
        self._brand_subtitle.setObjectName("Muted")
        brand_layout.addWidget(self._brand_title)
        brand_layout.addWidget(self._brand_subtitle)
        brand.setLayout(brand_layout)
        self._brand_frame = brand
        layout.addWidget(brand)

        top_row = QHBoxLayout()
        top_row.setSpacing(2)

        home_item = NavItem("home", "Home", "home")
        home_button = NavButton(home_item, self)
        home_button.setObjectName("SidebarHomeButton")
        self._buttons.append(home_button)
        top_row.addWidget(home_button, 1)
        top_row.addWidget(self._arrow_button, 0)
        layout.addLayout(top_row)

        nav_items = [
            NavItem("crosshairs", "Crosshairs", "crosshairs"),
            NavItem("creator", "Creator", "creator"),
            NavItem("games", "Games", "games"),
        ]
        for item in nav_items:
            button = NavButton(item, self)
            self._buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        beta_item = NavItem("beta", "Zoom", "zoom")
        self._beta_button = NavButton(beta_item, self)
        self._beta_button.setVisible(False)
        self._buttons.append(self._beta_button)
        layout.addWidget(self._beta_button)

        settings_item = NavItem("settings", "Settings", "settings")
        self._settings_button = NavButton(settings_item, self)
        self._buttons.append(self._settings_button)
        layout.addWidget(self._settings_button)
        self.setLayout(layout)

    def _wire_signals(self) -> None:
        for button in self._buttons:
            button.clicked.connect(lambda checked=False, page=button.page_id: self.navigation_requested.emit(page))
        self._arrow_button.toggled_requested.connect(self.collapse_toggled.emit)

    def set_selected(self, page_id: str) -> None:
        for button in self._buttons:
            button.setChecked(button.page_id == page_id)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        for button in self._buttons:
            button.set_collapsed(collapsed)
        if self._brand_frame is not None:
            self._brand_frame.setVisible(not collapsed)
        if self._brand_title is not None:
            self._brand_title.setVisible(not collapsed)
        if self._brand_subtitle is not None:
            self._brand_subtitle.setVisible(not collapsed)
        self._arrow_button.animate_to_collapsed(collapsed)

    def set_beta_visible(self, visible: bool) -> None:
        if self._beta_button is None:
            return
        self._beta_button.setVisible(visible)

    @property
    def collapsed(self) -> bool:
        return self._collapsed
