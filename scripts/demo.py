"""Launch the demo app or updater for install a|b."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_updater(install: str, once: bool) -> int:
    cfg = ROOT / "installs" / install / "config.json"
    if not cfg.is_file():
        sys.exit(f"missing {cfg}; run scripts/bootstrap_installs.py first")
    cmd = [sys.executable, str(ROOT / "client" / "updater.py"), "--config", str(cfg)]
    if once:
        cmd.append("--once")
    return subprocess.call(cmd)


def run_app(install: str) -> int:
    install_root = (ROOT / "installs" / install).resolve()
    marker = install_root / "current_version"
    if not marker.is_file():
        sys.exit(f"no current_version in {install_root}; run updater first")
    version = marker.read_text(encoding="utf-8").strip()
    app = install_root / "versions" / version / "color_app.py"
    env = os.environ.copy()
    env["INSTALL_ROOT"] = str(install_root)
    env["INSTALL_NAME"] = f"install-{install}"
    return subprocess.call([sys.executable, str(app)], env=env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["updater", "app"])
    parser.add_argument("--install", choices=["a", "b"], required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.command == "updater":
        raise SystemExit(run_updater(args.install, args.once))
    raise SystemExit(run_app(args.install))


if __name__ == "__main__":
    main()
