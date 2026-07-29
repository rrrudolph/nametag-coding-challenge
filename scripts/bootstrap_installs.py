"""Write install configs for demo clients a and b from terraform outputs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = ROOT / "infra"
INSTALLS = ROOT / "installs"


def tf_raw(name: str) -> str:
    return subprocess.check_output(
        ["terraform", f"-chdir={INFRA_DIR}", "output", "-raw", name],
        text=True,
    ).strip()


def tf_json(name: str):
    return json.loads(
        subprocess.check_output(
            ["terraform", f"-chdir={INFRA_DIR}", "output", "-json", name],
            text=True,
        )
    )


def main() -> None:
    clients = tf_json("install_clients")
    check_url = tf_raw("check_url")
    result_url = tf_raw("result_url")
    token_url = tf_raw("token_url")
    scopes = tf_json("oauth_scopes")

    for letter, creds in clients.items():
        root = INSTALLS / letter
        root.mkdir(parents=True, exist_ok=True)
        (root / "versions").mkdir(exist_ok=True)
        cfg = {
            "name": f"install-{letter}",
            "install_root": str(root.resolve()),
            "check_url": check_url,
            "result_url": result_url,
            "token_url": token_url,
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "scope_check": scopes["check"],
            "scope_telemetry": scopes["telemetry"],
        }
        path = root / "config.json"
        path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
