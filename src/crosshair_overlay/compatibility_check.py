from __future__ import annotations


def probe_screen_capture(screen: object, index: int) -> dict[str, object]:
    """Test a tiny desktop capture and immediately discard its pixels."""
    geometry = screen.geometry()
    result: dict[str, object] = {
        "display": f"Display {index + 1}",
        "x": int(geometry.x()),
        "y": int(geometry.y()),
        "width": int(geometry.width()),
        "height": int(geometry.height()),
        "devicePixelRatio": float(screen.devicePixelRatio()),
        "captureAvailable": False,
        "status": "Capture test did not return an image.",
    }
    if geometry.width() < 1 or geometry.height() < 1:
        result["status"] = "Display reported empty geometry."
        return result
    x = max(0, min(geometry.width() - 2, geometry.width() // 2))
    y = max(0, min(geometry.height() - 2, geometry.height() // 2))
    try:
        sample = screen.grabWindow(0, x, y, min(2, geometry.width()), min(2, geometry.height()))
        available = not sample.isNull()
    except Exception as exc:  # noqa: BLE001 - expose a safe exception class, not desktop contents.
        result["status"] = f"Capture failed ({type(exc).__name__})."
        return result
    result["captureAvailable"] = available
    result["status"] = "Desktop capture returned a test frame." if available else "Desktop capture returned no frame."
    return result
