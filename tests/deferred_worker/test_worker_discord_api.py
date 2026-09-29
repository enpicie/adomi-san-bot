"""jobs/deferred_worker/worker_discord_api.py — the parts that decide what the
organizer is told when Discord rejects a create."""
import unittest
from unittest.mock import Mock

import worker_discord_api


def _response(status_code, payload=None, json_error=None):
    response = Mock()
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload
    return response


class TestExtractDiscordError(unittest.TestCase):
    """MIRROR of src/utils/discord_api_helper.py _extract_discord_error."""

    def test_field_level_message_wins_over_the_generic_top_level_one(self):
        # A rejected end time comes back as "Invalid Form Body" at the top level;
        # only the field error says what to fix.
        response = _response(400, {
            "code": 50035,
            "message": "Invalid Form Body",
            "errors": {"scheduled_end_time": {"_errors": [
                {"code": "BASE_TYPE_BAD_TIME", "message": "Scheduled end time must be after scheduled start time"}
            ]}},
        })

        self.assertEqual(
            worker_discord_api._extract_discord_error(response),
            "Scheduled end time must be after scheduled start time",
        )

    def test_top_level_message_used_when_there_are_no_field_errors(self):
        response = _response(403, {"code": 50013, "message": "Missing Permissions"})

        self.assertEqual(worker_discord_api._extract_discord_error(response), "Missing Permissions")

    def test_non_json_body_falls_back_to_the_status(self):
        response = _response(502, json_error=ValueError("not json"))

        self.assertEqual(worker_discord_api._extract_discord_error(response), "HTTP 502")


if __name__ == "__main__":
    unittest.main()
