from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QLabel, QTextBrowser, QVBoxLayout, QWidget

from ...app_metadata import APP_NAME, APP_VERSION, GITHUB_LATEST_RELEASE_URL
from ..components import PageHeader, SectionCard


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._notes = QTextBrowser(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        root.addWidget(
            PageHeader(
                "About",
                "Build information, update links, and latest UI refactor notes.",
                eyebrow="Application",
                parent=self,
            )
        )

        info = SectionCard(APP_NAME, f"Version {APP_VERSION}", object_name="HeroCard", parent=self)
        info.body.addWidget(QLabel(f"Latest release: {GITHUB_LATEST_RELEASE_URL}", self))
        root.addWidget(info)

        changelog = SectionCard("UI Changelog", "Recent redesign and UX improvements.", parent=self)
        self._notes.setReadOnly(True)
        self._notes.setOpenExternalLinks(False)
        self._notes.setMarkdown(self._read_changelog())
        self._apply_markdown_theme()
        changelog.body.addWidget(self._notes)
        root.addWidget(changelog, 1)
        self.setLayout(root)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange, QEvent.Type.ApplicationPaletteChange}:
            self._apply_markdown_theme()

    def _apply_markdown_theme(self) -> None:
        base = self.palette().color(self.backgroundRole())
        is_light = base.lightness() > 165
        text = "#162033" if is_light else "#E7EEFF"
        muted = "#3D4F6A" if is_light else "#9FAAC0"
        link = "#2E67A6" if is_light else "#7EB8FF"
        heading = "#0F223F" if is_light else "#F2F6FF"
        self._notes.document().setDefaultStyleSheet(
            (
                f"body {{ color: {text}; line-height: 1.38; }}"
                f"h1, h2, h3, h4 {{ color: {heading}; margin-top: 0.55em; margin-bottom: 0.28em; }}"
                f"p, li {{ color: {text}; }}"
                f"ul, ol {{ margin-top: 0.2em; margin-bottom: 0.32em; }}"
                f"code {{ color: {muted}; }}"
                f"a {{ color: {link}; text-decoration: none; }}"
            )
        )

    def _read_changelog(self) -> str:
        candidates = [
            Path.cwd() / "UI_CHANGELOG.md",
            Path.cwd() / "CHANGELOG.md",
        ]
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text:
                return text
        return "No changelog file found."
