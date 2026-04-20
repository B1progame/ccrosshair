from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python installer/make_windows_icon.py <input.svg> <output.ico>")
        return 1

    source = Path(sys.argv[1]).resolve()
    target = Path(sys.argv[2]).resolve()

    if not source.exists():
        print(f"[icon] Source SVG not found: {source}")
        return 1

    app = QGuiApplication([])
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        print(f"[icon] Invalid SVG: {source}")
        return 1

    size = 256
    padding = 12
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        renderer.render(painter, QRectF(padding, padding, size - (padding * 2), size - (padding * 2)))
    finally:
        painter.end()

    target.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(target), "ICO"):
        print(f"[icon] Failed to write icon: {target}")
        return 1

    print(f"[icon] Wrote Windows icon: {target}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
