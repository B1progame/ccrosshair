from __future__ import annotations


def effective_zoom_max_percent(output_side: int, available_source_side: int, minimum_crop: int = 18,
                               minimum: int = 200, maximum: int = 1600) -> int:
    """Report the highest zoom before the source crop reaches its minimum."""
    output = max(1, int(output_side))
    available = max(1, int(available_source_side))
    floor = max(1, int(minimum_crop))
    return max(minimum, min(maximum, int(round(output * 100 / max(floor, available)))))


def stepped_zoom_percent(current: int, direction: int, step: int = 25, minimum: int = 200, maximum: int = 1600) -> int:
    """Apply a bounded zoom-wheel/key increment without losing crop limits."""
    sign = 1 if direction > 0 else -1 if direction < 0 else 0
    return max(minimum, min(maximum, int(current) + sign * max(1, int(step))))


class ZoomActivationLatch:
    """Convert the configured physical hotkey into hold or edge-triggered toggle state."""

    def __init__(self) -> None:
        self._held = False
        self._toggled = False

    def reset(self) -> None:
        self._held = False
        self._toggled = False

    def update(self, physical_down: bool, enabled: bool, typing: bool, mode: str) -> bool:
        if not enabled:
            self.reset()
            return False
        physical_down = bool(physical_down)
        rising = physical_down and not self._held
        self._held = physical_down
        if mode == "toggle":
            if rising and not typing:
                self._toggled = not self._toggled
            return self._toggled
        return physical_down and not typing
