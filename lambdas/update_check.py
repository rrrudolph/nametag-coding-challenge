"""Update-check lambda (behind API Gateway + Cognito authorizer).

Client polls with its currently-running version. We resolve the effective
version for that client (client pin ?? platform pin ?? latest) and return
either 304 or version metadata + a presigned S3 download URL.
"""

from __future__ import annotations

import json
import os
import time

import boto3

PINS_TABLE = os.environ["PINS_TABLE"]
RELEASES_TABLE = os.environ["RELEASES_TABLE"]
RELEASES_BUCKET = os.environ["RELEASES_BUCKET"]
PRESIGN_TTL_SECONDS = 900
LATEST_CACHE_TTL_SECONDS = 5  # short for live demos; raise for production

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
pins_table = dynamodb.Table(PINS_TABLE)
releases_table = dynamodb.Table(RELEASES_TABLE)

# Warm-invocation cache: platform -> (record, fetched_at)
_latest_cache: dict[str, tuple[dict, float]] = {}


def _response(status: int, body=None) -> dict:
    if body is None:
        return {"statusCode": status, "body": ""}
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _client_id_from_event(event: dict) -> str:
    """Install identity = Cognito `sub` (app client id from client_credentials)."""
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]


def _item_to_release(item: dict) -> dict:
    version = item["version"]
    if version == "latest":
        version = item["target_version"]
    return {
        "version": version,
        "sha256": item["sha256"],
        "s3_key": item["s3_key"],
        "size": int(item["size"]),
    }


def _resolve_pin(client_id: str, platform: str) -> str | None:
    """Most-specific pin wins: client pin, then platform pin, then None."""
    keys = [
        {"pin_key": f"client#{client_id}"},
        {"pin_key": f"platform#{platform}"},
    ]
    result = dynamodb.batch_get_item(
        RequestItems={PINS_TABLE: {"Keys": keys}},
    )
    items = {i["pin_key"]: i for i in result.get("Responses", {}).get(PINS_TABLE, [])}
    for key in (f"client#{client_id}", f"platform#{platform}"):
        if key in items and "version" in items[key]:
            return items[key]["version"]
    return None


def _get_latest_release(platform: str) -> dict:
    cached = _latest_cache.get(platform)
    if cached is not None and time.time() - cached[1] < LATEST_CACHE_TTL_SECONDS:
        return cached[0]

    resp = releases_table.get_item(Key={"version": "latest", "platform": platform})
    item = resp.get("Item")
    if not item:
        raise KeyError(f"no latest release for platform {platform}")
    record = _item_to_release(item)
    _latest_cache[platform] = (record, time.time())
    return record


def _get_release(version: str, platform: str) -> dict:
    resp = releases_table.get_item(Key={"version": version, "platform": platform})
    item = resp.get("Item")
    if not item:
        raise KeyError(f"release {version} / {platform} not found")
    return _item_to_release(item)


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
    platform = params.get("platform")
    if not client_version or not platform:
        return _response(400, {"error": "current_version and platform are required"})

    try:
        pinned = _resolve_pin(client_id, platform)
        release = (
            _get_release(pinned, platform)
            if pinned
            else _get_latest_release(platform)
        )
    except KeyError as exc:
        return _response(404, {"error": str(exc)})

    if release["version"] == client_version:
        return _response(304)

    return _response(
        200,
        {
            "version": release["version"],
            "sha256": release["sha256"],
            "size": release["size"],
            "download_url": _presign_download(release["s3_key"]),
        },
    )
