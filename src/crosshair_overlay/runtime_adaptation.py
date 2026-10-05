from __future__ import annotations


class GpuRuntimeAdaptation:
    """Hysteresis controller for optional GPU-heat/load-driven preview cadence."""

    def __init__(self) -> None:
        self._hot_samples = 0
        self._cool_samples = 0
        self._override: str | None = None
        self.status = "Automatic adaptation is off; the selected mode is locked."

    def reset(self, status: str = "Automatic adaptation is off; the selected mode is locked.") -> None:
        self._hot_samples = 0
        self._cool_samples = 0
        self._override = None
        self.status = status

    def unavailable(self) -> None:
        self._hot_samples = 0
        self._cool_samples = 0
        self.status = "GPU telemetry unavailable; the selected mode is unchanged."

    def sample(self, base_mode: str, temperature_c: int, utilization_percent: int) -> str:
        if temperature_c >= 85 or utilization_percent >= 95:
            self._hot_samples += 1
            self._cool_samples = 0
            if self._hot_samples >= 3:
                self._override = "eco" if base_mode not in {"quiet", "eco"} else None
                self.status = (
                    f"GPU load/temperature high ({temperature_c}°C, {utilization_percent}%); preview cadence reduced to Eco."
                    if self._override else
                    f"GPU load/temperature high ({temperature_c}°C, {utilization_percent}%); selected mode is already low activity."
                )
        elif temperature_c <= 75 and utilization_percent <= 80:
            self._cool_samples += 1
            self._hot_samples = 0
            if self._cool_samples >= 6:
                self._override = None
                self.status = "GPU load/temperature stable; selected mode restored."
        else:
            self._hot_samples = 0
            self._cool_samples = 0
            if self._override:
                self.status = "Preview cadence remains in Eco while GPU load settles."
            else:
                self.status = f"GPU stable ({temperature_c}°C, {utilization_percent}%); selected mode active."
        return self._override or base_mode

    @property
    def override(self) -> str | None:
        return self._override

    def effective_mode(self, base_mode: str) -> str:
        return self._override or base_mode
