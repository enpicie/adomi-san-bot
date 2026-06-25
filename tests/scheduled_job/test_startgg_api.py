import os
import sys

# Scheduled job modules read env vars at import time (via scheduled_job_constants).
os.environ["REGION"] = "us-east-1"
os.environ["DISCORD_BOT_TOKEN_SECRET_NAME"] = "test-secret-name"
os.environ["DYNAMODB_TABLE_NAME"] = "test-table"
os.environ["REMOVE_ROLE_QUEUE_URL"] = "https://sqs.test"
os.environ["STARTGG_SECRET_NAME"] = "test-startgg-secret"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "scheduled_job"))

import unittest
from unittest.mock import Mock, patch

import requests

import startgg_api

_VALID_URL = "https://www.start.gg/tournament/midweek/event/singles"
# 2026-04-10T21:00:00Z as a unix timestamp.
_START_AT_UNIX = 1775854800
_START_AT_ISO = "2026-04-10T21:00:00Z"


def _mock_response(ok=True, status_code=200, json_data=None, raises_json=False):
    resp = Mock()
    resp.ok = ok
    resp.status_code = status_code
    if raises_json:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = json_data or {}
    return resp


class TestExtractSlug(unittest.TestCase):
    def test_extracts_slug(self):
        self.assertEqual(startgg_api.extract_startgg_slug(_VALID_URL), "tournament/midweek/event/singles")

    def test_invalid_url_returns_none(self):
        self.assertIsNone(startgg_api.extract_startgg_slug("https://example.com/not-a-tournament"))

    def test_none_url_returns_none(self):
        self.assertIsNone(startgg_api.extract_startgg_slug(None))


class TestGetEventStartTimeUtc(unittest.TestCase):
    def _run(self, response=None, request_exc=None):
        with patch("startgg_api.requests") as mock_requests, \
             patch("startgg_api.constants") as mock_constants:
            mock_constants.get_startgg_api_token.return_value = "token"
            mock_requests.RequestException = requests.RequestException
            if request_exc is not None:
                mock_requests.post.side_effect = request_exc
            else:
                mock_requests.post.return_value = response
            result = startgg_api.get_event_start_time_utc(_VALID_URL)
        return result

    def test_invalid_url_skips_request(self):
        with patch("startgg_api.requests") as mock_requests:
            result = startgg_api.get_event_start_time_utc("https://example.com/nope")
        self.assertIsNone(result)
        mock_requests.post.assert_not_called()

    def test_successful_response_returns_iso(self):
        resp = _mock_response(json_data={"data": {"event": {"id": "1", "startAt": _START_AT_UNIX}}})
        self.assertEqual(self._run(response=resp), _START_AT_ISO)

    def test_null_event_returns_none(self):
        resp = _mock_response(json_data={"data": {"event": None}})
        self.assertIsNone(self._run(response=resp))

    def test_null_start_at_returns_none(self):
        resp = _mock_response(json_data={"data": {"event": {"id": "1", "startAt": None}}})
        self.assertIsNone(self._run(response=resp))

    def test_non_ok_response_returns_none(self):
        resp = _mock_response(ok=False, status_code=500)
        self.assertIsNone(self._run(response=resp))

    def test_request_exception_returns_none(self):
        self.assertIsNone(self._run(request_exc=requests.RequestException("boom")))

    def test_non_json_body_returns_none(self):
        resp = _mock_response(raises_json=True)
        self.assertIsNone(self._run(response=resp))


if __name__ == "__main__":
    unittest.main()
