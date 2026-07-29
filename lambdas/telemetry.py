"""Telemetry lambda — ingest client update success/failure reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import boto3

RESULTS_TABLE = os.environ["RESULTS_TABLE"]
RESULT_TTL_DAYS = 30

REQUIRED_FIELDS = ("version", "success")

dynamodb = boto3.resource("dynamodb")
results_table = dynamodb.Table(RESULTS_TABLE)


def _client_id_from_event(event: dict) -> str:
    # Cognito `sub` = install identity; see update_check._client_id_from_event.
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]


def _store_result(client_id: str, payload: dict) -> None:
    now = datetime.now(timezone.utc)
    item = {
        "client_id": client_id,
        "reported_at": now.isoformat(),
        "version": str(payload["version"]),
        "success": bool(payload["success"]),
        "expires_at": int((now + timedelta(days=RESULT_TTL_DAYS)).timestamp()),
    }
    for key in ("from_version", "error", "platform", "attempt"):
        if key in payload and payload[key] is not None:
            item[key] = payload[key]
    results_table.put_item(Item=item)


def handler(event: dict, context) -> dict:
    client_id = _client_id_from_event(event)

    try:
        payload = json.loads(event.get("body") or "")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON"})}

    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        return {"statusCode": 400, "body": json.dumps({"error": f"missing: {missing}"})}

    if not isinstance(payload["success"], bool):
        return {"statusCode": 400, "body": json.dumps({"error": "success must be bool"})}

    _store_result(client_id, payload)
    return {"statusCode": 201, "body": json.dumps({"ok": True})}
