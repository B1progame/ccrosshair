from __future__ import annotations

import winreg
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from .app_settings import ThemeMode


@dataclass(frozen=True)
class ThemePalette:
    base: str
    shell: str
    panel: str
    panel_alt: str
    text: str
    muted_text: str
    border: str
    border_strong: str
    hover: str
    selected: str
    selected_strong: str
    accent: str
    accent_soft: str
    accent_text: str
    success: str
    warning: str
    danger: str


class ThemeManager:
    def __init__(self, app: QApplication) -> None:
        self._app = app
        self.resolved_mode = ThemeMode.DARK

    def apply(self, theme_mode: str, accent_hex: str) -> None:
        resolved_mode = self._resolve_mode(theme_mode)
        self.resolved_mode = resolved_mode
        accent = self._normalize_color(accent_hex, "#A923E2")
        palette = self._build_palette(resolved_mode=resolved_mode, accent=accent)
        self._app.setStyleSheet(self._build_stylesheet(palette))

    def _resolve_mode(self, mode: str) -> ThemeMode:
        if mode == ThemeMode.LIGHT.value:
            return ThemeMode.LIGHT
        if mode == ThemeMode.DARK.value:
            return ThemeMode.DARK
        return self._read_system_mode()

    def _read_system_mode(self) -> ThemeMode:
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return ThemeMode.LIGHT if int(value) == 1 else ThemeMode.DARK
        except OSError:
            return ThemeMode.DARK

    def _build_palette(self, resolved_mode: ThemeMode, accent: str) -> ThemePalette:
        if resolved_mode == ThemeMode.LIGHT:
            return ThemePalette(
                base="#F4F7FB",
                shell="#EAF0F8",
                panel="#FFFFFF",
                panel_alt="#F0F4FA",
                text="#162033",
                muted_text="#5B687C",
                border="#D7E0EE",
                border_strong="#BCC9DD",
                hover="#EFF5FF",
                selected=self._mix(accent, "#FFFFFF", 0.12),
                selected_strong=self._mix(accent, "#FFFFFF", 0.22),
                accent=accent,
                accent_soft=self._mix(accent, "#FFFFFF", 0.16),
                accent_text=self._contrast_text(accent),
                success="#12A36D",
                warning="#C77D13",
                danger="#D9485F",
            )
        return ThemePalette(
            base="#0E131B",
            shell="#121926",
            panel="#171F2C",
            panel_alt="#1D2737",
            text="#EDF2FF",
            muted_text="#9FAAC0",
            border="#29364A",
            border_strong="#3A4A63",
            hover="#202C3F",
            selected=self._mix(accent, "#151C27", 0.18),
            selected_strong=self._mix(accent, "#151C27", 0.3),
            accent=accent,
            accent_soft=self._mix(accent, "#141B26", 0.25),
            accent_text=self._contrast_text(accent),
            success="#27C07D",
            warning="#F0A43A",
            danger="#F06C7E",
        )

    def _build_stylesheet(self, p: ThemePalette) -> str:
        base = f"""
        QWidget {{
            background: {p.base};
            color: {p.text};
            font-family: "Segoe UI Variable Text", "Segoe UI";
            font-size: 13px;
        }}
        QLabel {{
            background: transparent;
        }}
        QWidget#OverlayWindow, QWidget#OverlayCrosshair {{
            background: transparent;
            border: none;
        }}
        QFrame#appShell {{
            background: {p.shell};
            border-radius: 24px;
        }}
        QFrame#sidebar {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {self._mix(p.panel_alt, p.shell, 0.92)},
                stop: 1 {self._mix(p.panel, p.shell, 0.9)}
            );
            border: 1px solid {self._mix(p.border, p.shell, 0.92)};
            border-radius: 20px;
        }}
        QFrame#contentSurface {{
            background: {self._mix(p.panel, p.base, 0.96)};
            border: 1px solid {self._mix(p.border, p.base, 0.9)};
            border-radius: 22px;
        }}
        QFrame#PageHeader {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {self._mix(p.accent, p.panel, 0.18)},
                stop: 0.5 {self._mix("#53D0C8", p.panel_alt, 0.08)},
                stop: 1 {self._mix(p.panel_alt, p.panel, 0.92)}
            );
            border: 1px solid {self._mix(p.accent, p.border, 0.32)};
            border-radius: 18px;
        }}
        QLabel#PageEyebrow {{
            color: {self._mix(p.accent, p.text, 0.72)};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        QLabel#PageTitle {{
            font-size: 28px;
            font-weight: 700;
        }}
        QLabel#PageSubTitle {{
            color: {p.muted_text};
            font-size: 13px;
        }}
        QLabel#CardTitle {{
            font-size: 16px;
            font-weight: 700;
        }}
        QLabel#MetricValue {{
            font-size: 21px;
            font-weight: 700;
        }}
        QLabel#Muted {{
            color: {p.muted_text};
        }}
        QLabel#InfoChip, QLabel#AccentChip {{
            padding: 4px 10px;
            border-radius: 11px;
            border: 1px solid {p.border};
            background: {self._mix(p.panel_alt, p.panel, 0.78)};
        }}
        QLabel#AccentChip {{
            background: {p.accent_soft};
            border: 1px solid {self._mix(p.accent, p.border, 0.55)};
            color: {p.text};
        }}
        QFrame#Card {{
            background: {self._mix(p.panel, p.base, 0.98)};
            border: 1px solid {p.border};
            border-radius: 18px;
        }}
        QFrame#HeroCard {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {self._mix(p.accent, p.panel, 0.2)},
                stop: 0.45 {self._mix("#3DC7D3", p.panel_alt, 0.07)},
                stop: 1 {self._mix(p.panel_alt, p.panel, 0.9)}
            );
            border: 1px solid {self._mix(p.accent, p.border, 0.36)};
            border-radius: 20px;
        }}
        QFrame#SubtleCard {{
            background: {self._mix(p.panel_alt, p.panel, 0.9)};
            border: 1px solid {self._mix(p.border, p.panel, 0.9)};
            border-radius: 16px;
        }}
        QFrame#EditorCanvasCard {{
            background: {self._mix(p.panel, p.base, 0.985)};
            border: 1px solid {self._mix(p.accent, p.border, 0.22)};
            border-radius: 18px;
        }}
        QPushButton {{
            background: {self._mix(p.panel_alt, p.panel, 0.74)};
            border: 1px solid {p.border};
            border-radius: 12px;
            padding: 9px 14px;
            font-weight: 600;
            min-height: 34px;
        }}
        QPushButton:hover {{
            background: {p.hover};
            border-color: {self._mix(p.accent, p.border, 0.42)};
        }}
        QPushButton:pressed {{
            background: {self._mix(p.hover, p.base, 0.82)};
        }}
        QPushButton:disabled {{
            color: {self._mix(p.muted_text, p.panel, 0.82)};
            background: {self._mix(p.panel_alt, p.panel, 0.56)};
            border-color: {self._mix(p.border, p.panel, 0.62)};
        }}
        QPushButton#PrimaryButton {{
            background: {p.accent};
            color: {p.accent_text};
            border: 1px solid {self._mix(p.accent, "#000000", 0.78)};
        }}
        QPushButton#PrimaryButton:hover {{
            background: {self._mix(p.accent, "#FFFFFF", 0.9)};
        }}
        QPushButton#GhostButton {{
            background: transparent;
            border: 1px solid {self._mix(p.accent, p.border, 0.32)};
            color: {p.text};
        }}
        QPushButton#DangerButton {{
            background: {self._mix(p.danger, p.panel, 0.18)};
            border: 1px solid {self._mix(p.danger, p.border, 0.5)};
            color: {p.text};
        }}
        QPushButton#DrawerCloseButton {{
            background: {self._mix(p.danger, p.panel, 0.2)};
            border: 1px solid {self._mix(p.danger, p.border, 0.55)};
            color: {self._mix("#FFD7DE", p.danger, 0.55)};
            border-radius: 12px;
            font-weight: 700;
            min-height: 28px;
            padding: 0px;
        }}
        QPushButton#DrawerCloseButton:hover {{
            background: {self._mix(p.danger, p.panel, 0.3)};
            border-color: {self._mix(p.danger, p.border_strong, 0.8)};
        }}
        QPushButton#NeutralButton {{
            background: {self._mix(p.border, p.panel_alt, 0.54)};
            border: 1px solid {self._mix(p.border_strong, p.border, 0.62)};
            color: {self._mix(p.text, p.muted_text, 0.9)};
        }}
        QPushButton#NeutralButton:hover {{
            background: {self._mix(p.border, p.panel_alt, 0.68)};
            border-color: {self._mix(p.border_strong, p.border, 0.84)};
        }}
        QPushButton#SidebarHomeButton, QPushButton#SidebarNavButton {{
            text-align: left;
            padding: 10px 12px;
            border-radius: 14px;
            font-weight: 600;
        }}
        QPushButton#SidebarHomeButton:checked, QPushButton#SidebarNavButton:checked {{
            background: {p.selected_strong};
            border: 1px solid {self._mix(p.accent, p.border, 0.65)};
        }}
        QFrame#ThemeSwitchCard {{
            background: {self._mix(p.panel_alt, p.panel, 0.86)};
            border: 1px solid {self._mix(p.border, p.panel, 0.92)};
            border-radius: 14px;
        }}
        QFrame#ThemeSwitchIndicator {{
            background: {self._mix(p.accent, p.panel_alt, 0.26)};
            border: 1px solid {self._mix(p.accent, p.border, 0.52)};
            border-radius: 11px;
        }}
        QPushButton#ThemeSwitchOption {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 11px;
            padding: 7px 6px;
            font-weight: 700;
        }}
        QPushButton#ThemeSwitchOption:hover {{
            border-color: {self._mix(p.accent, p.border, 0.4)};
            background: {self._mix(p.hover, p.panel, 0.6)};
        }}
        QPushButton#ThemeSwitchOption[active="true"] {{
            background: transparent;
            border-color: transparent;
        }}
        QToolButton {{
            background: {self._mix(p.panel_alt, p.panel, 0.74)};
            border: 1px solid {p.border};
            border-radius: 12px;
            padding: 8px 10px;
            min-height: 34px;
        }}
        QToolButton:hover {{
            background: {p.hover};
        }}
        QToolButton:checked {{
            background: {p.selected_strong};
            border: 1px solid {self._mix(p.accent, p.border, 0.65)};
        }}
        QComboBox, QLineEdit, QSpinBox, QTextEdit, QKeySequenceEdit {{
            background: {self._mix(p.panel_alt, p.panel, 0.8)};
            border: 1px solid {p.border};
            border-radius: 12px;
            padding: 8px 10px;
            min-height: 34px;
        }}
        QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QTextEdit:hover, QKeySequenceEdit:hover {{
            border-color: {self._mix(p.accent, p.border, 0.42)};
        }}
        QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QKeySequenceEdit:focus {{
            border-color: {self._mix(p.accent, p.border_strong, 0.72)};
        }}
        QPushButton#CardFavoriteButton {{
            min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
            padding: 0; border-radius: 7px; font-size: 14px;
        }}
        QLabel#ValidationMessage {{ color: {p.danger}; font-size: 11px; }}
        QLineEdit[invalid="true"] {{ border-color: {p.danger}; }}
        QComboBox::drop-down {{
            width: 28px;
            border: none;
        }}
        QListWidget, QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea#FolderScrollArea, QScrollArea#GalleryScrollArea {{
            background: {self._mix(p.panel_alt, p.panel, 0.86)};
            border: 1px solid {self._mix(p.border, p.panel, 0.86)};
            border-radius: 14px;
        }}
        QWidget#FolderScrollViewport, QWidget#GalleryScrollViewport {{
            background: {self._mix(p.panel_alt, p.panel, 0.86)};
            border-radius: 12px;
        }}
        QSlider::groove:horizontal {{
            height: 6px;
            border-radius: 3px;
            background: {self._mix(p.border, p.panel, 0.72)};
        }}
        QSlider::sub-page:horizontal {{
            border-radius: 3px;
            background: {self._mix(p.accent, p.panel, 0.78)};
        }}
        QSlider::handle:horizontal {{
            width: 18px;
            margin: -6px 0;
            border-radius: 9px;
            background: {p.accent};
            border: 1px solid {self._mix(p.accent, "#000000", 0.76)};
        }}
        QCheckBox {{
            background: transparent;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 5px;
            border: 1px solid {p.border_strong};
            background: {self._mix(p.panel_alt, p.panel, 0.8)};
        }}
        QCheckBox::indicator:checked {{
            background: {p.accent};
            border-color: {self._mix(p.accent, "#000000", 0.76)};
        }}
        QScrollBar:vertical {{
            width: 12px;
            background: transparent;
            margin: 4px 2px 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {self._mix(p.border_strong, p.panel_alt, 0.64)};
            border-radius: 6px;
            min-height: 28px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
            border: none;
        }}
        QScrollBar:horizontal {{
            height: 12px;
            background: transparent;
            margin: 2px 4px 2px 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {self._mix(p.border_strong, p.panel_alt, 0.64)};
            border-radius: 6px;
            min-width: 28px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
            border: none;
        }}
        QToolTip {{
            background: {p.panel};
            color: {p.text};
            border: 1px solid {p.border};
            padding: 6px 8px;
        }}
        """
        return base + self._load_global_qss(p)

    def _load_global_qss(self, p: ThemePalette) -> str:
        qss_path = Path(__file__).resolve().parent / "assets" / "styles" / "global.qss"
        try:
            content = qss_path.read_text(encoding="utf-8")
        except OSError:
            return ""
        tokens = {
            "%%PANEL%%": p.panel,
            "%%PANEL_ALT%%": p.panel_alt,
            "%%TEXT%%": p.text,
            "%%MUTED_TEXT%%": p.muted_text,
            "%%BORDER%%": p.border,
            "%%HOVER%%": p.hover,
            "%%ACCENT_MID%%": self._mix(p.accent, p.border, 0.45),
        }
        for token, value in tokens.items():
            content = content.replace(token, value)
        return "\n" + content + "\n"

    def _normalize_color(self, raw: str, fallback: str) -> str:
        color = QColor(raw)
        if not color.isValid():
            color = QColor(fallback)
        return color.name().upper()

    def _mix(self, foreground: str, background: str, fg_weight: float) -> str:
        fg = QColor(foreground)
        bg = QColor(background)
        weight = max(0.0, min(1.0, fg_weight))
        r = int(round((fg.red() * weight) + (bg.red() * (1.0 - weight))))
        g = int(round((fg.green() * weight) + (bg.green() * (1.0 - weight))))
        b = int(round((fg.blue() * weight) + (bg.blue() * (1.0 - weight))))
        return QColor(r, g, b).name().upper()

    @staticmethod
    def _contrast_text(accent: str) -> str:
        color = QColor(accent)

        def linear(component: int) -> float:
            value = component / 255.0
            return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

        luminance = 0.2126 * linear(color.red()) + 0.7152 * linear(color.green()) + 0.0722 * linear(color.blue())
        return "#111615" if luminance > 0.42 else "#FFFFFF"
