"""Client-side self-updater for the color-app demo.

Polls the update lambda, downloads a release zip, runs selftest, swaps the
current_version pointer. The running GUI watches that pointer and relaunches
itself into the new version's code when it changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Demo-friendly poll; bump for production.
POLL_INTERVAL_SECONDS = 5
BACKOFF_BASE_SECONDS = 60
BACKOFF_MAX_SECONDS = 24 * 3600
TOKEN_SKEW_SECONDS = 60

# Server-supplied version strings become local path components
# (staging/<version>, versions/<version>), so reject anything that could
# escape the install root before we build a path from it.
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_version(version: str) -> str:
    if not _VERSION_RE.match(version):
        raise ValueError(f"unsafe version string from server: {version!r}")
    return version


def platform_id() -> str:
    return f"{sys.platform}/{platform.machine()}"


class InstallConfig:
    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.path = path
        self.name = data["name"]
        self.install_root = Path(data["install_root"])
        self.check_url = data["check_url"]
        self.result_url = data["result_url"]
        self.token_url = data["token_url"]
        self.client_id = data["client_id"]
        self.client_secret = data["client_secret"]
        self.scope_check = data.get("scope_check", "update-api/check")
        self.scope_telemetry = data.get("scope_telemetry", "update-api/telemetry")
        self._token: str | None = None
        self._token_expires_at = 0.0

    def ensure_dirs(self) -> None:
        (self.install_root / "versions").mkdir(parents=True, exist_ok=True)
        (self.install_root / "staging").mkdir(parents=True, exist_ok=True)


def get_auth_token(cfg: InstallConfig) -> str:
    """Fetch a client_credentials token covering check + telemetry scopes."""
    now = time.time()
    if cfg._token and now < cfg._token_expires_at - TOKEN_SKEW_SECONDS:
        return cfg._token

    scope = f"{cfg.scope_check} {cfg.scope_telemetry}"
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "scope": scope,
        }
    ).encode()
    req = Request(
        cfg.token_url,
        data=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    cfg._token = payload["access_token"]
    cfg._token_expires_at = now + int(payload.get("expires_in", 3600))
    return cfg._token


def current_version(cfg: InstallConfig) -> str | None:
    marker = cfg.install_root / "current_version"
    if not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip() or None


def check_for_update(cfg: InstallConfig) -> dict | None:
    version = current_version(cfg) or "0.0.0"
    qs = urlencode({"current_version": version, "platform": platform_id()})
    token = get_auth_token(cfg)
    req = Request(
        f"{cfg.check_url}?{qs}",
        headers={"authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status == 304:
                return None
            update = json.loads(resp.read().decode())
    except HTTPError as exc:
        if exc.code == 304:
            return None
        raise
    validate_version(update["version"])
    return update


def download_binary(update: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Cheap disk-space check (Windows + POSIX).
    free = shutil.disk_usage(dest.parent).free
    if free < int(update["size"]) * 2:
        raise RuntimeError(f"insufficient disk space: free={free} need~{update['size']*2}")

    with urlopen(update["download_url"], timeout=120) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def verify_sha256(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest() == expected


def run_tests(extract_dir: Path) -> bool:
    selftest = extract_dir / "selftest.py"
    if not selftest.is_file():
        return False
    proc = subprocess.run(
        [sys.executable, str(selftest)],
        cwd=str(extract_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode == 0


def atomic_swap(cfg: InstallConfig, extract_dir: Path, version: str) -> None:
    target = cfg.install_root / "versions" / version
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(extract_dir, target)

    marker = cfg.install_root / "current_version"
    tmp = cfg.install_root / "current_version.tmp"
    tmp.write_text(version + "\n", encoding="utf-8")
    os.replace(tmp, marker)


def report_result(
    cfg: InstallConfig,
    version: str,
    success: bool,
    error: str | None = None,
    from_version: str | None = None,
) -> None:
    body = {
        "version": version,
        "success": success,
        "platform": platform_id(),
        "from_version": from_version,
        "error": error,
    }
    token = get_auth_token(cfg)
    req = Request(
        cfg.result_url,
        data=json.dumps(body).encode(),
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception as exc:
        print(f"[{cfg.name}] telemetry failed: {exc}", flush=True)


def try_update(cfg: InstallConfig, update: dict) -> bool:
    from_version = current_version(cfg)
    zip_path = cfg.install_root / "staging" / f"{update['version']}.zip"
    extract_dir = cfg.install_root / "staging" / update["version"]
    try:
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        download_binary(update, zip_path)
        if not verify_sha256(zip_path, update["sha256"]):
            raise RuntimeError("sha256 mismatch (corrupt download)")
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        if not run_tests(extract_dir):
            raise RuntimeError("selftest failed")
        atomic_swap(cfg, extract_dir, update["version"])
    except Exception as exc:
        print(f"[{cfg.name}] update to {update['version']} failed: {exc}", flush=True)
        report_result(cfg, update["version"], False, error=str(exc), from_version=from_version)
        return False
    finally:
        if zip_path.exists():
            zip_path.unlink()
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

    print(f"[{cfg.name}] now running {update['version']}", flush=True)
    report_result(cfg, update["version"], True, from_version=from_version)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Nametag demo client updater")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to install config JSON (credentials + install_root)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Poll once and exit (useful for scripts)",
    )
    args = parser.parse_args()

    cfg = InstallConfig(Path(args.config))
    cfg.ensure_dirs()
    failures: dict[str, int] = {}
    next_allowed: dict[str, float] = {}

    print(
        f"[{cfg.name}] updater started root={cfg.install_root} "
        f"platform={platform_id()} current={current_version(cfg)}",
        flush=True,
    )

    while True:
        try:
            update = check_for_update(cfg)
            if update:
                ver = update["version"]
                if time.time() >= next_allowed.get(ver, 0):
                    ok = try_update(cfg, update)
                    if ok:
                        failures.pop(ver, None)
                        next_allowed.pop(ver, None)
                    else:
                        n = failures.get(ver, 0) + 1
                        failures[ver] = n
                        delay = min(BACKOFF_BASE_SECONDS * (2 ** (n - 1)), BACKOFF_MAX_SECONDS)
                        next_allowed[ver] = time.time() + delay
                        print(f"[{cfg.name}] backing off {ver} for {delay}s", flush=True)
            else:
                print(f"[{cfg.name}] up to date ({current_version(cfg)})", flush=True)
        except Exception as exc:
            print(f"[{cfg.name}] poll error: {exc}", flush=True)

        if args.once:
            break
        # Jitter so a fleet doesn't stampede the server (or S3) in lockstep
        # the moment a release lands.
        time.sleep(POLL_INTERVAL_SECONDS * random.uniform(1.0, 1.25))


if __name__ == "__main__":
    main()
