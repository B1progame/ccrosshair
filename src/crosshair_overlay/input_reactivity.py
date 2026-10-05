from __future__ import annotations

import math


def pulse_envelope(elapsed_ms: float, duration_ms: int) -> float:
    """Deterministic monotonic-time pulse envelope from 0 → 1 → 0."""
    duration = max(1, int(duration_ms))
    progress = min(1.0, max(0.0, float(elapsed_ms) / duration))
    return math.sin(math.pi * progress) if progress < 1.0 else 0.0
