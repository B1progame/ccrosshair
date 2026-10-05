"""Crosshair overlay package."""

from .runtime_bootstrap import configure_frozen_qt_runtime


# This runs before .app imports PySide6, preventing foreign Qt DLLs from winning.
configure_frozen_qt_runtime()

from .app import run

__all__ = ["run"]
