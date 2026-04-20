from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PageHeader(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str,
        eyebrow: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeader")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)

        self._eyebrow_label: QLabel | None = None
        if eyebrow:
            self._eyebrow_label = QLabel(eyebrow, self)
            self._eyebrow_label.setObjectName("PageEyebrow")
            layout.addWidget(self._eyebrow_label)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("PageTitle")
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle, self)
        self._subtitle_label.setObjectName("PageSubTitle")
        self._subtitle_label.setWordWrap(True)
        layout.addWidget(self._subtitle_label)
        self.setLayout(layout)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle)


class SectionCard(QFrame):
    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        object_name: str = "Card",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)
        if title:
            title_label = QLabel(title, self)
            title_label.setObjectName("CardTitle")
            self._layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle, self)
            subtitle_label.setObjectName("Muted")
            subtitle_label.setWordWrap(True)
            self._layout.addWidget(subtitle_label)
        self.setLayout(self._layout)

    @property
    def body(self) -> QVBoxLayout:
        return self._layout


class InfoChip(QLabel):
    def __init__(self, text: str, accent: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("AccentChip" if accent else "InfoChip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SubtleCard")
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(4)
        label_widget = QLabel(label, self)
        label_widget.setObjectName("Muted")
        value_widget = QLabel(value, self)
        value_widget.setObjectName("MetricValue")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        self.setLayout(layout)


class ActionRow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.setLayout(layout)

    @property
    def body(self) -> QHBoxLayout:
        return self.layout()  # type: ignore[return-value]
