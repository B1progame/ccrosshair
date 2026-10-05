from __future__ import annotations

import math


class FireInputTracker:
    """Turn foreground mouse/key state into press or held-cadence events."""

    def __init__(self) -> None:
        self._held = False
        self._last_pulse_at = 0.0

    def reset(self) -> None:
        self._held = False
        self._last_pulse_at = 0.0

    def update(self, mouse_down: bool, key_down: bool, now: float, cadence_ms: int) -> bool:
        down = bool(mouse_down or key_down)
        cadence = max(0, min(1000, int(cadence_ms)))
        triggered = down and (
            not self._held
            or (cadence > 0 and self._last_pulse_at > 0 and (float(now) - self._last_pulse_at) * 1000 >= cadence)
        )
        if triggered:
            self._last_pulse_at = float(now)
        elif not down:
            self._last_pulse_at = 0.0
        self._held = down
        return triggered


def pulse_envelope(elapsed_ms: float, duration_ms: int) -> float:
    """Deterministic monotonic-time pulse envelope from 0 → 1 → 0."""
    duration = max(1, int(duration_ms))
    progress = min(1.0, max(0.0, float(elapsed_ms) / duration))
    return math.sin(math.pi * progress) if progress < 1.0 else 0.0
