from __future__ import annotations

import os
import sys


def _add_src_to_path() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def main() -> int:
    _add_src_to_path()
    from crosshair_overlay import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
