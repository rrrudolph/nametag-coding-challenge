"""Pin (or unpin) a demo install to a specific version."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = ROOT / "infra"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", choices=["a", "b"], required=True)
    parser.add_argument("--version")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()

    cfg = json.loads(
        (ROOT / "installs" / args.install / "config.json").read_text(encoding="utf-8")
    )
    pin_key = f"client#{cfg['client_id']}"
    table_name = subprocess.check_output(
        ["terraform", f"-chdir={INFRA_DIR}", "output", "-raw", "pins_table"],
        text=True,
    ).strip()
    table = boto3.resource("dynamodb").Table(table_name)

    if args.clear:
        table.delete_item(Key={"pin_key": pin_key})
        print(f"cleared {pin_key}")
        return

    if not args.version:
        parser.error("--version required unless --clear")

    item = {
        "pin_key": pin_key,
        "version": args.version,
        "expires_at": int(time.time()) + 7 * 86400,
    }
    table.put_item(Item=item)
    print(item)


if __name__ == "__main__":
    main()
