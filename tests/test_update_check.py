"""Unit tests for the update-check lambda's pin resolution and handler."""

from unittest import mock

import pytest

import update_check

PLATFORM = "win32/AMD64"
RELEASE_V1 = {"version": "1.0.0", "sha256": "aa", "s3_key": "k1", "size": 10}
RELEASE_V2 = {"version": "2.0.0", "sha256": "bb", "s3_key": "k2", "size": 20}


@pytest.fixture(autouse=True)
def clear_latest_cache():
    update_check._latest_cache.clear()
    yield


def _batch_response(items):
    return {"Responses": {update_check.PINS_TABLE: items}}


def _event(params, sub="client-abc"):
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": sub}}}},
        "queryStringParameters": params,
    }


class TestResolvePin:
    def test_client_pin_beats_platform_pin(self):
        items = [
            {"pin_key": f"platform#{PLATFORM}", "version": "1.5.0"},
            {"pin_key": "client#client-abc", "version": "1.0.0"},
        ]
        with mock.patch.object(
            update_check.dynamodb, "batch_get_item", return_value=_batch_response(items)
        ):
            assert update_check._resolve_pin("client-abc", PLATFORM) == "1.0.0"

    def test_platform_pin_when_no_client_pin(self):
        items = [{"pin_key": f"platform#{PLATFORM}", "version": "1.5.0"}]
        with mock.patch.object(
            update_check.dynamodb, "batch_get_item", return_value=_batch_response(items)
        ):
            assert update_check._resolve_pin("client-abc", PLATFORM) == "1.5.0"

    def test_no_pins_returns_none(self):
        with mock.patch.object(
            update_check.dynamodb, "batch_get_item", return_value=_batch_response([])
        ):
            assert update_check._resolve_pin("client-abc", PLATFORM) is None


class TestItemToRelease:
    def test_latest_alias_maps_to_target_version(self):
        item = {
            "version": "latest",
            "target_version": "2.0.0",
            "sha256": "bb",
            "s3_key": "k2",
            "size": 20,
        }
        assert update_check._item_to_release(item)["version"] == "2.0.0"


class TestHandler:
    def test_missing_params_is_400(self):
        resp = update_check.handler(_event({}), None)
        assert resp["statusCode"] == 400

    def test_up_to_date_is_304(self):
        with (
            mock.patch.object(update_check, "_resolve_pin", return_value=None),
            mock.patch.object(update_check, "_get_latest_release", return_value=RELEASE_V2),
        ):
            resp = update_check.handler(
                _event({"current_version": "2.0.0", "platform": PLATFORM}), None
            )
        assert resp["statusCode"] == 304

    def test_behind_latest_gets_download_url(self):
        with (
            mock.patch.object(update_check, "_resolve_pin", return_value=None),
            mock.patch.object(update_check, "_get_latest_release", return_value=RELEASE_V2),
            mock.patch.object(
                update_check, "_presign_download", return_value="https://signed"
            ) as presign,
        ):
            resp = update_check.handler(
                _event({"current_version": "1.0.0", "platform": PLATFORM}), None
            )
        assert resp["statusCode"] == 200
        assert '"https://signed"' in resp["body"]
        presign.assert_called_once_with("k2")

    def test_pin_forces_downgrade(self):
        """Client already on 2.0.0 but pinned to 1.0.0 -> gets 1.0.0 (rollback)."""
        with (
            mock.patch.object(update_check, "_resolve_pin", return_value="1.0.0"),
            mock.patch.object(update_check, "_get_release", return_value=RELEASE_V1),
            mock.patch.object(update_check, "_presign_download", return_value="https://signed"),
        ):
            resp = update_check.handler(
                _event({"current_version": "2.0.0", "platform": PLATFORM}), None
            )
        assert resp["statusCode"] == 200
        assert '"1.0.0"' in resp["body"]

    def test_unknown_platform_is_404(self):
        with (
            mock.patch.object(update_check, "_resolve_pin", return_value=None),
            mock.patch.object(
                update_check, "_get_latest_release", side_effect=KeyError("no latest")
            ),
        ):
            resp = update_check.handler(
                _event({"current_version": "1.0.0", "platform": "beos/ppc"}), None
            )
        assert resp["statusCode"] == 404
