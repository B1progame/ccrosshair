from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget


@dataclass(frozen=True)
class SidebarItem:
    page_id: str
    label: str
    icon: QIcon


class SidebarButton(QPushButton):
    def __init__(self, item: SidebarItem, parent: QWidget | None = None) -> None:
        super().__init__(item.label, parent)
        self._item = item
        self._collapsed = False
        self._label = item.label
        self.setObjectName("SidebarNavButton")
        self.setCheckable(True)
        self.setIcon(item.icon)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._apply_collapsed_style()

    @property
    def page_id(self) -> str:
        return self._item.page_id

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.setText("" if self._collapsed else self._label)
        self._apply_collapsed_style()

    def set_label(self, label: str) -> None:
        self._label = str(label)
        self.setText("" if self._collapsed else self._label)

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def _apply_collapsed_style(self) -> None:
        if self._collapsed:
            self.setStyleSheet("text-align: center; padding: 8px 0px;")
        else:
            self.setStyleSheet("text-align: left; padding: 8px 10px;")
