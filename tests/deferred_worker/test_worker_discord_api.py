"""jobs/deferred_worker/worker_discord_api.py — the parts that decide what the
organizer is told when Discord rejects a create."""
import unittest
from unittest.mock import Mock, patch

import worker_discord_api

import utils.discord_api_helper as src_discord_helper


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

    def test_nested_field_error_is_surfaced_instead_of_invalid_form_body(self):
        response = _response(400, {
            "code": 50035,
            "message": "Invalid Form Body",
            "errors": {"entity_metadata": {"location": {"_errors": [
                {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 100 or fewer in length."}
            ]}}},
        })

        self.assertEqual(
            worker_discord_api._extract_discord_error(response, worker_discord_api._SCHEDULED_EVENT_FIELD_LABELS),
            "Location: Must be 100 or fewer in length.",
        )


class TestCreateScheduledEventRejections(unittest.TestCase):
    def _create(self, response):
        with patch.object(worker_discord_api, "discord_request", return_value=response):
            return worker_discord_api.create_scheduled_event(
                "g1", name="Weekly", location="Online",
                scheduled_start_time="2099-01-01T18:00:00Z", scheduled_end_time="2099-01-01T21:00:00Z",
            )

    def test_missing_permission_names_the_permission_to_grant(self):
        with self.assertRaises(ValueError) as ctx:
            self._create(_response(403, {"code": 50013, "message": "Missing Permissions"}))
        self.assertEqual(str(ctx.exception), worker_discord_api.MISSING_EVENT_PERMISSION_MESSAGE)

    def test_messages_match_the_src_twin(self):
        self.assertEqual(worker_discord_api.MISSING_EVENT_PERMISSION_MESSAGE, src_discord_helper.MISSING_EVENT_PERMISSION_MESSAGE)
        self.assertEqual(worker_discord_api._SCHEDULED_EVENT_FIELD_LABELS, src_discord_helper._SCHEDULED_EVENT_FIELD_LABELS)


if __name__ == "__main__":
    unittest.main()
