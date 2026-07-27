"""Update-check lambda (behind API Gateway + Cognito authorizer).

Client polls with its currently-running version. We resolve the effective
version for that client (pin ?? latest) and return either "no update"
(304-equivalent) or version metadata + a presigned S3 download URL.
"""

from __future__ import annotations

import os
import time

import boto3

PINS_TABLE = os.environ.get("PINS_TABLE", "client-version-pins")
RELEASES_TABLE = os.environ.get("RELEASES_TABLE", "releases")
RELEASES_BUCKET = os.environ.get("RELEASES_BUCKET", "releases-bucket")
PRESIGN_TTL_SECONDS = 900
LATEST_CACHE_TTL_SECONDS = 60

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# Warm-invocation cache for the latest release record: (record, fetched_at).
_latest_cache: tuple[dict, float] | None = None


def _client_id_from_event(event: dict) -> str:
    """Client identity for pin lookups: the Cognito `sub` claim.

    Each install is provisioned with its own credentials (client_credentials
    flow), so `sub` maps 1:1 to an install. Crucially it's signed into the
    JWT — unlike a self-reported hardware/app ID header, a client can't
    spoof it to dodge its own pin or read another client's.
    """
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]


def _resolve_pin(client_id: str, platform: str) -> str | None:
    """Most-specific pin wins: client pin, then platform pin, then None.

    A bad release usually breaks a platform cohort (OS/arch combo), not a
    single machine — so pins can target either scope in one sparse table:

        pin_key = "client#<sub>"          # this one install
        pin_key = "platform#<os>/<arch>"  # everyone on that platform

    One BatchGetItem fetches both keys; most polls miss both (cheap).
    Platform is self-reported by the client, which is fine here: lying about
    your platform only gets you the wrong binary — it isn't an escalation.
    """
    # TODO: BatchGetItem on PINS_TABLE for [f"client#{client_id}", f"platform#{platform}"]
    # TODO: return client pin if present, else platform pin, else None
    return None


def _get_latest_release(platform: str) -> dict:
    """Latest release record for a platform, cached across warm invocations.

    Binaries are per-platform, so release records are keyed by (version,
    platform). Record shape: {"version": str, "sha256": str, "s3_key": str,
    "size": int}
    """
    global _latest_cache
    # TODO: cache per platform (dict keyed by platform), not one global tuple
    if _latest_cache is not None and time.time() - _latest_cache[1] < LATEST_CACHE_TTL_SECONDS:
        return _latest_cache[0]
    # TODO: fetch from RELEASES_TABLE (e.g. GetItem on a well-known "latest" key)
    record: dict = {}
    _latest_cache = (record, time.time())
    return record


def _get_release(version: str, platform: str) -> dict:
    """Release record for a specific (possibly pinned) version + platform."""
    # TODO: GetItem on RELEASES_TABLE by (version, platform)
    raise NotImplementedError


def _presign_download(s3_key: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": RELEASES_BUCKET, "Key": s3_key},
        ExpiresIn=PRESIGN_TTL_SECONDS,
    )


def handler(event: dict, context) -> dict:
    client_id = _client_id_from_event(event)
    params = event.get("queryStringParameters") or {}
    client_version = params.get("current_version")
    platform = params.get("platform")  # e.g. "linux/amd64", "darwin/arm64"
    # TODO: 400 if current_version or platform missing

    pinned = _resolve_pin(client_id, platform)
    release = _get_release(pinned, platform) if pinned else _get_latest_release(platform)
    effective_version = release["version"]

    if effective_version == client_version:
        # No update (and no presigning work) on the common path.
        return {"statusCode": 304, "body": ""}

    # TODO: json.dumps body, set content-type header
    return {
        "statusCode": 200,
        "body": {
            "version": effective_version,
            "sha256": release["sha256"],
            "size": release["size"],
            "download_url": _presign_download(release["s3_key"]),
        },
    }
