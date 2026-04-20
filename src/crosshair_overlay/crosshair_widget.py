from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from .config import OverlayStyle
from .overlay_renderer import draw_overlay_style


class CrosshairWidget(QWidget):
    """Paints the currently selected overlay style."""

    def __init__(self, style: OverlayStyle, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayCrosshair")
        self._style = style
        self._apply_size()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_style(self, style: OverlayStyle) -> bool:
        if style == self._style:
            return False
        self._style = style
        self._apply_size()
        self.update()
        return True

    def _apply_size(self) -> None:
        size = self._style.canvas_size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming convention)
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        draw_overlay_style(painter, self.rect(), self._style)
