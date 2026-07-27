"""Telemetry lambda (same API Gateway + Cognito auth flow as update_check).

Ingests client update results: success/failure, versions involved, error
detail. Acts as the logging interface for the fleet.
"""

from __future__ import annotations

import json
import os

RESULTS_TABLE = os.environ.get("RESULTS_TABLE", "update-results")

REQUIRED_FIELDS = ("version", "success")


def _client_id_from_event(event: dict) -> str:
    # Cognito `sub` = install identity; see update_check._client_id_from_event
    # for the reasoning. Results are attributed to the same ID pins use.
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]


def _store_result(client_id: str, payload: dict) -> None:
    """Persist the result to DynamoDB. Exponential backoff handles log spam."""
    raise NotImplementedError


def handler(event: dict, context) -> dict:
    client_id = _client_id_from_event(event)

    try:
        payload = json.loads(event.get("body") or "")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON"})}

    missing = [f for f in REQUIRED_FIELDS if f not in payload]
    if missing:
        return {"statusCode": 400, "body": json.dumps({"error": f"missing: {missing}"})}

    # Expected optional fields: from_version, error, os, arch, attempt
    _store_result(client_id, payload)

    return {"statusCode": 201, "body": json.dumps({"ok": True})}
