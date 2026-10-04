from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPalette
from PySide6.QtWidgets import QPushButton, QSizePolicy, QToolButton, QWidget

from ..crosshairs.models import CrosshairDefinition
from ..overlay_renderer import draw_overlay_style


class CrosshairCardButton(QToolButton):
    favorite_clicked = Signal(str)
    _preview_cache: OrderedDict[tuple[str, int, int, int, int], QPixmap] = OrderedDict()
    _preview_cache_limit = 256
    _render_version = 3
    CARD_HEIGHT = 186

    def __init__(
        self,
        definition: CrosshairDefinition,
        cache_key_builder: Callable[[CrosshairDefinition], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self._state_selected = False
        self._state_active = False
        self._state_batch = False
        self._accent_color = ""
        self._cache_key_builder = cache_key_builder or (lambda item: item.style_id)
        self.setAccessibleName(definition.display_name)
        self.setToolTip(definition.display_name)
        self._favorite_button = QPushButton(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self.setMinimumSize(176, self.CARD_HEIGHT)
        self.setMaximumHeight(self.CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._favorite_button.setFixedSize(28, 28)
        self._favorite_button.setMinimumSize(28, 28)
        self._favorite_button.setObjectName("CardFavoriteButton")
        self._favorite_button.setAccessibleName("Toggle favorite")
        self._favorite_button.clicked.connect(self._emit_favorite)
        self._refresh_favorite()

    def set_state(self, selected: bool, active: bool, batch_selected: bool) -> None:
        self._state_selected = bool(selected)
        self._state_active = bool(active)
        self._state_batch = bool(batch_selected)
        self._refresh_favorite()
        self.update()

    def sync_definition(self, definition: CrosshairDefinition) -> None:
        self.definition = definition
        self.setAccessibleName(definition.display_name)
        self.setToolTip(definition.display_name)
        self._refresh_favorite()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._favorite_button.move(self.width() - self._favorite_button.width() - 10, 10)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = self.rect().adjusted(2, 2, -2, -2)

        palette = self.palette()
        panel = palette.base().color()
        panel_alt = palette.window().color()
        text = palette.text().color()
        is_light = panel.lightness() > 128

        if is_light:
            background = self._mix(panel, panel_alt, 0.7)
            border = self._mix(text, panel, 0.24)
            preview_bg = self._mix(panel, QColor("#0E1624"), 0.08)
            family_text_color = self._mix(text, panel, 0.58)
        else:
            background = QColor("#182131")
            border = QColor("#2F3B52")
            preview_bg = QColor("#101925")
            family_text_color = QColor("#94A6C3")

        accent = QColor(self._accent_color) if QColor(self._accent_color).isValid() else self.palette().color(QPalette.ColorRole.Highlight)
        if self._state_batch or self._state_selected:
            background = self._mix(panel, accent, 0.13 if self._state_batch else 0.09)
            border = accent
        if self._state_active:
            border = QColor("#36B37E") if is_light else QColor("#54D69A")
        painter.setPen(QPen(border, 2))
        painter.setBrush(background)
        painter.drawRoundedRect(outer, 14, 14)
        if self._state_batch:
            painter.setPen(QPen(accent, 2))
            painter.drawEllipse(outer.right() - 18, outer.top() + 8, 10, 10)
        if self._state_active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#36B37E") if is_light else QColor("#54D69A"))
            painter.drawRoundedRect(QRectF(outer.left() + 10, outer.top() + 10, 6, 6), 3, 3)

        preview = QRectF(outer.left() + 12, outer.top() + 12, outer.width() - 24, outer.height() - 66)
        pixmap = self._preview_pixmap(int(preview.width()), int(preview.height()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(preview_bg)
        painter.drawRoundedRect(preview, 12, 12)
        if not pixmap.isNull():
            painter.drawPixmap(preview.toRect(), pixmap)

        title_rect = QRectF(outer.left() + 12, outer.bottom() - 46, outer.width() - 24, 22)
        family_rect = QRectF(outer.left() + 12, outer.bottom() - 24, outer.width() - 24, 16)
        metrics = painter.fontMetrics()
        title_text = metrics.elidedText(self.definition.display_name, Qt.TextElideMode.ElideRight, int(title_rect.width()))
        family_text = metrics.elidedText(self.definition.family, Qt.TextElideMode.ElideRight, int(family_rect.width()))
        painter.setPen(self.palette().text().color())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title_text)
        painter.setPen(family_text_color)
        painter.drawText(family_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, family_text)

    def _preview_pixmap(self, width: int, height: int) -> QPixmap:
        dpr = max(1.0, self.devicePixelRatioF())
        ratio = int(round(dpr * 100))
        key = (self._cache_key_builder(self.definition) + repr(self.definition.style), max(1, width), max(1, height), ratio, self._render_version)
        pixmap = self._preview_cache.get(key)
        if pixmap is not None:
            self._preview_cache.move_to_end(key)
            return pixmap
        pixmap = QPixmap(max(1, round(key[1] * dpr)), max(1, round(key[2] * dpr)))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw_overlay_style(painter, QRectF(0, 0, key[1], key[2]), self.definition.style.scaled(210))
        painter.end()
        self._preview_cache[key] = pixmap
        if len(self._preview_cache) > self._preview_cache_limit:
            self._preview_cache.popitem(last=False)
        return pixmap

    def _refresh_favorite(self) -> None:
        self._favorite_button.setText("\u2665" if self.definition.is_favorite else "\u2661")
        self._favorite_button.setObjectName("PrimaryButton" if self.definition.is_favorite else "GhostButton")
        self._favorite_button.setToolTip("Remove Favorite" if self.definition.is_favorite else "Add Favorite")
        self._favorite_button.style().unpolish(self._favorite_button)
        self._favorite_button.style().polish(self._favorite_button)
        self._favorite_button.raise_()

    def set_accent_color(self, color_hex: str) -> None:
        if QColor(color_hex).isValid():
            self._accent_color = QColor(color_hex).name()
            self.update()

    def _emit_favorite(self) -> None:
        self.favorite_clicked.emit(self.definition.style_id)

    @staticmethod
    def _mix(foreground: QColor, background: QColor, fg_weight: float) -> QColor:
        weight = max(0.0, min(1.0, fg_weight))
        r = int(round((foreground.red() * weight) + (background.red() * (1.0 - weight))))
        g = int(round((foreground.green() * weight) + (background.green() * (1.0 - weight))))
        b = int(round((foreground.blue() * weight) + (background.blue() * (1.0 - weight))))
        return QColor(r, g, b)
