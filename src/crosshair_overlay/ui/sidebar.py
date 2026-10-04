from __future__ import annotations

from PySide6.QtCore import Property, QEvent, QPropertyAnimation, QEasingCurve, QPointF, QRect, QRectF, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..widgets.sidebar_button import SidebarButton, SidebarItem


def _build_nav_icon(icon_key: str, color_hex: str = "#8EA9CC") -> QIcon:
    size = 20
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color_hex), 1.9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if icon_key == "home":
        painter.drawLine(4, 10, 10, 4)
        painter.drawLine(10, 4, 16, 10)
        painter.drawRect(QRectF(5.5, 9.5, 9, 7))
    elif icon_key == "crosshairs":
        painter.drawRect(QRectF(4, 4, 12, 12))
        painter.drawLine(10, 4, 10, 16)
        painter.drawLine(4, 10, 16, 10)
    elif icon_key == "mine":
        painter.drawEllipse(QRectF(5, 4, 10, 10))
        painter.drawLine(10, 14, 10, 17)
    elif icon_key == "export":
        painter.drawLine(10, 4, 10, 12)
        painter.drawLine(7, 9, 10, 12)
        painter.drawLine(13, 9, 10, 12)
        painter.drawRect(QRectF(5, 13, 10, 3))
    elif icon_key == "creator":
        painter.drawLine(4, 15, 14, 5)
        painter.drawLine(14, 5, 16, 7)
        painter.drawLine(5, 14, 7, 16)
    elif icon_key == "games":
        path = QPainterPath()
        path.moveTo(QPointF(6, 5))
        path.lineTo(QPointF(15, 10))
        path.lineTo(QPointF(6, 15))
        path.closeSubpath()
        painter.drawPath(path)
    elif icon_key == "settings":
        painter.drawEllipse(QRectF(7, 7, 6, 6))
        painter.drawLine(10, 3, 10, 17)
        painter.drawLine(3, 10, 17, 10)
    elif icon_key == "about":
        painter.drawEllipse(QRectF(5, 4, 10, 10))
        painter.drawLine(10, 8, 10, 12)
        painter.drawPoint(10, 14)
    elif icon_key == "zoom":
        painter.drawEllipse(QRectF(4.5, 4.5, 8.5, 8.5))
        painter.drawLine(12.5, 12.5, 16.5, 16.5)
    elif icon_key == "theme_light":
        painter.drawEllipse(QRectF(6, 6, 8, 8))
        painter.drawLine(10, 2.5, 10, 4.5)
        painter.drawLine(10, 15.5, 10, 17.5)
        painter.drawLine(2.5, 10, 4.5, 10)
        painter.drawLine(15.5, 10, 17.5, 10)
        painter.drawLine(4.1, 4.1, 5.5, 5.5)
        painter.drawLine(14.5, 14.5, 15.9, 15.9)
        painter.drawLine(4.1, 15.9, 5.5, 14.5)
        painter.drawLine(14.5, 5.5, 15.9, 4.1)
    elif icon_key == "theme_dark":
        path = QPainterPath()
        path.moveTo(QPointF(13.0, 4.5))
        path.cubicTo(QPointF(9.2, 5.4), QPointF(6.8, 8.2), QPointF(6.8, 11.2))
        path.cubicTo(QPointF(6.8, 14.5), QPointF(9.4, 16.8), QPointF(12.5, 16.8))
        path.cubicTo(QPointF(14.2, 16.8), QPointF(15.7, 16.2), QPointF(16.9, 15.1))
        path.cubicTo(QPointF(16.3, 17.6), QPointF(14.0, 19.2), QPointF(11.2, 19.2))
        path.cubicTo(QPointF(7.3, 19.2), QPointF(4.2, 16.3), QPointF(4.2, 12.5))
        path.cubicTo(QPointF(4.2, 8.2), QPointF(7.8, 4.4), QPointF(12.3, 4.1))
        path.closeSubpath()
        painter.drawPath(path)
    elif icon_key == "theme_system":
        painter.drawRoundedRect(QRectF(4.5, 5.5, 11, 8), 1.8, 1.8)
        painter.drawLine(8.7, 15.5, 11.3, 15.5)
        painter.drawLine(10, 13.5, 10, 15.5)
        painter.drawLine(7.3, 17.2, 12.7, 17.2)
    elif icon_key == "quit":
        painter.drawLine(6, 6, 14, 14)
        painter.drawLine(6, 14, 14, 6)
        painter.drawLine(16, 4, 16, 16)
    else:
        painter.drawRect(QRectF(5, 5, 10, 10))
    painter.end()
    return QIcon(pixmap)


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
        self.setAccessibleName("Collapse or expand sidebar")
        self.setFixedSize(28, 28)
        self.clicked.connect(self.toggled_requested.emit)

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


class ThemeModeSwitcher(QFrame):
    mode_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ThemeSwitchCard")
        self.setMinimumHeight(38)
        self._modes: list[tuple[str, str, str]] = [
            ("light", "Light", "theme_light"),
            ("system", "System", "theme_system"),
            ("dark", "Dark", "theme_dark"),
        ]
        self._buttons: list[QPushButton] = []
        self._current_mode = "system"
        self._indicator = QFrame(self)
        self._indicator.setObjectName("ThemeSwitchIndicator")
        self._indicator_animation = QPropertyAnimation(self._indicator, b"geometry", self)
        self._indicator_animation.setDuration(220)
        self._indicator_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        for mode, label, icon_key in self._modes:
            button = QPushButton("", self)
            button.setObjectName("ThemeSwitchOption")
            button.setIcon(_build_nav_icon(icon_key))
            button.setIconSize(QSize(16, 16))
            button.setToolTip(label)
            button.setCheckable(True)
            button.setMinimumHeight(28)
            button.clicked.connect(lambda _checked=False, m=mode: self.set_mode(m, animated=True, emit_signal=True))
            layout.addWidget(button, 1)
            self._buttons.append(button)
        self.setLayout(layout)
        self._indicator.lower()
        self._sync_mode(animated=False)

    def set_icon_color(self, color_hex: str) -> None:
        for button, (_mode, label, icon_key) in zip(self._buttons, self._modes):
            button.setIcon(_build_nav_icon(icon_key, color_hex=color_hex))
            button.setToolTip(label)

    def set_mode(self, mode: str, animated: bool = True, emit_signal: bool = False) -> None:
        mode = mode.strip().lower()
        valid_modes = {item[0] for item in self._modes}
        if mode not in valid_modes:
            mode = "system"
        if mode == self._current_mode and not emit_signal:
            return
        self._current_mode = mode
        self._sync_mode(animated=animated)
        if emit_signal:
            self.mode_changed.emit(mode)

    def current_mode(self) -> str:
        return self._current_mode

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_mode(animated=False)

    def _sync_mode(self, animated: bool) -> None:
        target_rect = self._indicator_target_rect()
        for mode_button, (mode, _label, _icon_key) in zip(self._buttons, self._modes):
            active = mode == self._current_mode
            mode_button.blockSignals(True)
            mode_button.setChecked(active)
            mode_button.setProperty("active", active)
            mode_button.style().unpolish(mode_button)
            mode_button.style().polish(mode_button)
            mode_button.blockSignals(False)
        if target_rect.width() <= 0:
            return
        self._indicator.show()
        self._indicator.raise_()
        if not animated:
            self._indicator_animation.stop()
            self._indicator.setGeometry(target_rect)
            self._indicator.lower()
            return
        self._indicator_animation.stop()
        self._indicator_animation.setStartValue(self._indicator.geometry())
        self._indicator_animation.setEndValue(target_rect)
        self._indicator_animation.start()
        self._indicator.lower()

    def _indicator_target_rect(self) -> QRect:
        if not self._buttons:
            return QRect()
        target_index = next((idx for idx, item in enumerate(self._modes) if item[0] == self._current_mode), 1)
        button = self._buttons[target_index]
        geometry = button.geometry()
        return QRect(geometry.x(), geometry.y(), geometry.width(), geometry.height())


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    collapse_toggled = Signal()
    theme_mode_changed = Signal(str)
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self._collapsed = False
        self._buttons: list[SidebarButton] = []
        self._button_icon_keys: dict[SidebarButton, str] = {}
        self._settings_button: SidebarButton | None = None
        self._beta_button: SidebarButton | None = None
        self._quit_button = QPushButton("Quit", self)
        self._arrow_button = ChevronButton(self)
        self._brand_frame: QFrame | None = None
        self._section_labels: list[QLabel] = []
        self._theme_switcher = ThemeModeSwitcher(self)
        self._update_alert_active = False
        self._rainbow_hue = 0
        self._rainbow_timer = QTimer(self)
        self._rainbow_timer.setInterval(120)
        self._rainbow_timer.timeout.connect(self._tick_rainbow_alert)
        self._build_ui()
        self._wire_signals()
        self._refresh_icon_colors()

    def _add_section(self, layout: QVBoxLayout, title: str) -> None:
        label = QLabel(title, self)
        label.setObjectName("SidebarSectionLabel")
        layout.addWidget(label)
        self._section_labels.append(label)

    def _add_nav_button(self, layout: QVBoxLayout, page_id: str, label: str, icon_key: str) -> SidebarButton:
        icon = _build_nav_icon(icon_key, color_hex=self._sidebar_icon_color())
        button = SidebarButton(SidebarItem(page_id=page_id, label=label, icon=icon), self)
        self._buttons.append(button)
        self._button_icon_keys[button] = icon_key
        layout.addWidget(button)
        return button

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        brand = QFrame(self)
        brand.setObjectName("SubtleCard")
        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(12, 12, 12, 12)
        brand_layout.setSpacing(2)
        brand_title = QLabel("CC Crosshair", brand)
        brand_title.setObjectName("CardTitle")
        brand_subtitle = QLabel("Overlay Studio", brand)
        brand_subtitle.setObjectName("Muted")
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_subtitle)
        brand.setLayout(brand_layout)
        self._brand_frame = brand
        layout.addWidget(brand)

        top_row = QHBoxLayout()
        home_button = self._add_nav_button(top_row, "home", "Home", "home")
        home_button.setObjectName("SidebarHomeButton")
        top_row.addWidget(self._arrow_button, 0)
        layout.addLayout(top_row)

        self._add_section(layout, "Library")
        self._add_nav_button(layout, "crosshairs", "Crosshair Library", "crosshairs")
        self._add_nav_button(layout, "my_crosshairs", "My Crosshairs", "mine")
        self._add_nav_button(layout, "export", "Export", "export")

        self._add_section(layout, "Workspace")
        self._add_nav_button(layout, "creator", "Creator", "creator")
        self._add_nav_button(layout, "games", "Games", "games")
        self._beta_button = self._add_nav_button(layout, "beta", "Zoom", "zoom")
        self._beta_button.setVisible(False)

        layout.addStretch(1)

        self._add_section(layout, "System")
        layout.addWidget(self._theme_switcher)
        self._settings_button = self._add_nav_button(layout, "settings", "Settings", "settings")
        self._add_nav_button(layout, "about", "About", "about")
        self._quit_button.setObjectName("DangerButton")
        self._quit_button.setIcon(_build_nav_icon("quit", color_hex="#F3AAB3"))
        self._quit_button.setIconSize(QSize(18, 18))
        self._quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quit_button.setMinimumHeight(36)
        self._apply_quit_button_style()
        layout.addWidget(self._quit_button)
        self.setLayout(layout)

    def _wire_signals(self) -> None:
        for button in self._buttons:
            button.clicked.connect(lambda _checked=False, page=button.page_id: self.navigation_requested.emit(page))
        self._arrow_button.toggled_requested.connect(self.collapse_toggled.emit)
        self._theme_switcher.mode_changed.connect(self.theme_mode_changed.emit)
        self._quit_button.clicked.connect(self.quit_requested.emit)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationPaletteChange}:
            self._refresh_icon_colors()

    def set_selected(self, page_id: str) -> None:
        for button in self._buttons:
            button.setChecked(button.page_id == page_id)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        for button in self._buttons:
            button.set_collapsed(collapsed)
        if self._update_alert_active and self._settings_button is not None:
            self._settings_button.set_label("Settings !")
            self._tick_rainbow_alert()
        self._theme_switcher.setVisible(not collapsed)
        self._quit_button.setText("" if collapsed else "Quit")
        self._apply_quit_button_style()
        if self._brand_frame is not None:
            self._brand_frame.setVisible(not collapsed)
        for section in self._section_labels:
            section.setVisible(not collapsed)
        self._arrow_button.animate_to_collapsed(collapsed)

    def set_beta_visible(self, visible: bool) -> None:
        if self._beta_button is not None:
            self._beta_button.setVisible(visible)

    def set_theme_mode(self, mode: str) -> None:
        if mode.strip().lower() == self._theme_switcher.current_mode():
            return
        self._theme_switcher.set_mode(mode, animated=False, emit_signal=False)

    def _sidebar_icon_color(self) -> str:
        base = self.palette().color(self.backgroundRole())
        if base.lightness() > 165:
            return "#3F526C"
        return "#8EA9CC"

    def _quit_icon_color(self) -> str:
        base = self.palette().color(self.backgroundRole())
        if base.lightness() > 165:
            return "#A64758"
        return "#F3AAB3"

    def _refresh_icon_colors(self) -> None:
        nav_color = self._sidebar_icon_color()
        for button in self._buttons:
            icon_key = self._button_icon_keys.get(button)
            if not icon_key:
                continue
            button.setIcon(_build_nav_icon(icon_key, color_hex=nav_color))
        self._theme_switcher.set_icon_color(nav_color)
        self._quit_button.setIcon(_build_nav_icon("quit", color_hex=self._quit_icon_color()))

    def _apply_quit_button_style(self) -> None:
        if self._collapsed:
            self._quit_button.setStyleSheet("text-align:center; padding:8px 0px; border-radius:12px;")
        else:
            self._quit_button.setStyleSheet("text-align:left; padding:8px 10px; border-radius:12px;")

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def set_update_alert(self, active: bool) -> None:
        self._update_alert_active = bool(active)
        if self._settings_button is None:
            return
        if self._update_alert_active:
            self._settings_button.set_label("Settings !")
            self._rainbow_timer.start()
            self._tick_rainbow_alert()
            return
        self._rainbow_timer.stop()
        self._settings_button.set_label("Settings")
        self._settings_button.setStyleSheet("")

    def _tick_rainbow_alert(self) -> None:
        if not self._update_alert_active or self._settings_button is None:
            return
        self._rainbow_hue = (self._rainbow_hue + 17) % 360
        c1 = QColor.fromHsv(self._rainbow_hue, 180, 235).name()
        c2 = QColor.fromHsv((self._rainbow_hue + 90) % 360, 180, 220).name()
        text_align = "center" if self._settings_button.collapsed else "left"
        padding = "8px 0px" if self._settings_button.collapsed else "8px 10px"
        self._settings_button.setStyleSheet(
            f"text-align:{text_align}; padding:{padding};"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c1}, stop:1 {c2});"
            "border:1px solid rgba(255,255,255,0.35); color:#FFFFFF; border-radius:12px;"
        )
