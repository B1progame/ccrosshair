from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _add_src_to_path() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def main() -> int:
    _add_src_to_path()
    try:
        from crosshair_overlay import run

        return run()
    except Exception:
        log_root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CrosshairOverlay" / "logs"
        try:
            log_root.mkdir(parents=True, exist_ok=True)
            (log_root / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
