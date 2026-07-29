"""Minimal demo app: colored window showing the current version.

Displays the manifest that shipped with *this* copy of the code. Watches the
install's current_version pointer; when the pointer no longer matches the
running version, the app spawns the new version's process and exits — so the
window you see is always actually executing the pointed-at code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path

# Directory this copy of the code is running from (versions/<x.y.z>/ when
# installed, or the repo's app/ dir when run standalone).
HERE = Path(__file__).resolve().parent

POLL_MS = 500


def install_root() -> Path:
    return Path(os.environ.get("INSTALL_ROOT", HERE))


def pointed_version(root: Path) -> str | None:
    marker = root / "current_version"
    if not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip() or None


class ColorApp:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest = json.loads((HERE / "version.json").read_text(encoding="utf-8"))
        self.win = tk.Tk()
        self.win.title(os.environ.get("INSTALL_NAME", root.name))
        self.win.geometry("480x320")
        self.label = tk.Label(self.win, font=("Segoe UI", 32, "bold"), fg="#ffffff")
        self.label.pack(expand=True, fill="both")
        color = self.manifest["color"]
        self.win.configure(bg=color)
        self.label.configure(text=f"v{self.manifest['version']}", bg=color)
        self.win.after(POLL_MS, self.poll)

    def poll(self) -> None:
        try:
            target = pointed_version(self.root)
            if target and target != self.manifest["version"]:
                entry = self.root / "versions" / target / "color_app.py"
                # Updater flips the pointer only after the version dir is
                # fully installed, but stay defensive about partial state.
                if entry.is_file():
                    self.relaunch(entry)
                    return
        except Exception:
            pass
        self.win.after(POLL_MS, self.poll)

    def relaunch(self, entry: Path) -> None:
        print(f"relaunching into {entry}", flush=True)
        subprocess.Popen([sys.executable, str(entry)], env=os.environ.copy())
        self.win.destroy()

    def run(self) -> None:
        self.win.mainloop()


if __name__ == "__main__":
    ColorApp(install_root()).run()
