"""Self-test for a staged release directory. Exit 0 = good to swap."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    manifest = root / "version.json"
    app = root / "color_app.py"
    if not manifest.is_file() or not app.is_file():
        print("missing version.json or color_app.py")
        return 1
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for key in ("version", "color"):
        if key not in data:
            print(f"version.json missing {key}")
            return 1
    print(f"ok {data['version']} {data['color']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
