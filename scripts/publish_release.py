"""Build a color-app release zip, upload to S3, register as latest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
INFRA_DIR = ROOT / "infra"


def terraform_output(name: str) -> str:
    return subprocess.check_output(
        ["terraform", f"-chdir={INFRA_DIR}", "output", "-raw", name],
        text=True,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--color", required=True)
    args = parser.parse_args()

    plat = f"{sys.platform}/{platform.machine()}"
    zip_path = ROOT / "build" / f"{args.version}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {"version": args.version, "color": args.color}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("version.json", json.dumps(manifest) + "\n")
        for name in ("color_app.py", "selftest.py"):
            zf.write(APP_DIR / name, arcname=name)

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    size = zip_path.stat().st_size
    bucket = terraform_output("releases_bucket")
    table_name = terraform_output("releases_table")
    s3_key = f"{plat}/{args.version}/color-app.zip"

    boto3.client("s3").upload_file(str(zip_path), bucket, s3_key)
    table = boto3.resource("dynamodb").Table(table_name)
    item = {
        "version": args.version,
        "platform": plat,
        "sha256": digest,
        "s3_key": s3_key,
        "size": size,
    }
    table.put_item(Item=item)
    table.put_item(
        Item={
            "version": "latest",
            "platform": plat,
            "target_version": args.version,
            "sha256": digest,
            "s3_key": s3_key,
            "size": size,
        }
    )
    print(f"published {args.version} ({args.color}) -> latest")


if __name__ == "__main__":
    main()
