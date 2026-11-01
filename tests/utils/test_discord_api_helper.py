"""src/utils/discord_api_helper.py — what the organizer is told when Discord
rejects a scheduled-event create, update or delete."""
import unittest
from unittest.mock import Mock, patch

import utils.discord_api_helper as discord_helper
from utils.discord_api_helper import ScheduledEventParams

_PARAMS = ScheduledEventParams(
    name="Weekly", location="Online",
    scheduled_start_time="2099-01-01T18:00:00Z", scheduled_end_time="2099-01-01T21:00:00Z",
)

_MISSING_PERMISSIONS = {"code": 50013, "message": "Missing Permissions"}
_LOCATION_TOO_LONG = {
    "code": 50035,
    "message": "Invalid Form Body",
    "errors": {"entity_metadata": {"location": {"_errors": [
        {"code": "BASE_TYPE_MAX_LENGTH", "message": "Must be 100 or fewer in length."}
    ]}}},
}


def _response(status_code, payload=None, json_error=None):
    response = Mock()
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload
    return response


class TestExtractDiscordError(unittest.TestCase):
    def test_nested_field_error_is_surfaced_instead_of_invalid_form_body(self):
        self.assertEqual(
            discord_helper._extract_discord_error(_response(400, _LOCATION_TOO_LONG)),
            "Must be 100 or fewer in length.",
        )

    def test_known_field_gets_its_label(self):
        self.assertEqual(
            discord_helper._extract_discord_error(
                _response(400, _LOCATION_TOO_LONG), discord_helper._SCHEDULED_EVENT_FIELD_LABELS
            ),
            "Location: Must be 100 or fewer in length.",
        )

    def test_top_level_message_used_when_there_are_no_field_errors(self):
        self.assertEqual(discord_helper._extract_discord_error(_response(403, _MISSING_PERMISSIONS)), "Missing Permissions")

    def test_non_json_body_falls_back_to_the_status(self):
        self.assertEqual(discord_helper._extract_discord_error(_response(502, json_error=ValueError("no"))), "HTTP 502")


class TestScheduledEventRejections(unittest.TestCase):
    def _call(self, response, fn, *args):
        with patch.object(discord_helper, "_request", return_value=response):
            return fn(*args)

    def test_create_without_permission_names_the_permission_to_grant(self):
        with self.assertRaises(ValueError) as ctx:
            self._call(_response(403, _MISSING_PERMISSIONS), discord_helper.create_scheduled_event, "g1", _PARAMS)
        self.assertEqual(str(ctx.exception), discord_helper.MISSING_EVENT_PERMISSION_MESSAGE)
        self.assertIn("Create Events", str(ctx.exception))

    def test_create_validation_error_says_which_field_and_why(self):
        with self.assertRaises(ValueError) as ctx:
            self._call(_response(400, _LOCATION_TOO_LONG), discord_helper.create_scheduled_event, "g1", _PARAMS)
        self.assertIn("create the event", str(ctx.exception))
        self.assertIn("Location: Must be 100 or fewer in length.", str(ctx.exception))
        self.assertNotIn("Invalid Form Body", str(ctx.exception))

    def test_update_rejection_raises_a_readable_message(self):
        with self.assertRaises(ValueError) as ctx:
            self._call(_response(403, _MISSING_PERMISSIONS), discord_helper.update_scheduled_event, "g1", "e1", _PARAMS)
        self.assertEqual(str(ctx.exception), discord_helper.MISSING_EVENT_PERMISSION_MESSAGE)

    def test_update_of_an_active_event_still_signals_the_start_time_lock(self):
        locked = {"code": 50035, "message": "Invalid Form Body", "errors": {"scheduled_start_time": {"_errors": [
            {"code": "GUILD_SCHEDULED_EVENT_SCHEDULE_INVALID_START_BY_STATUS", "message": "locked"}
        ]}}}
        with self.assertRaises(discord_helper.EventAlreadyActiveError):
            self._call(_response(400, locked), discord_helper.update_scheduled_event, "g1", "e1", _PARAMS)

    def test_delete_without_permission_names_the_permission_to_grant(self):
        with self.assertRaises(ValueError) as ctx:
            self._call(_response(403, _MISSING_PERMISSIONS), discord_helper.delete_scheduled_event, "g1", "e1")
        self.assertEqual(str(ctx.exception), discord_helper.MISSING_EVENT_PERMISSION_MESSAGE)

    def test_delete_of_an_event_already_gone_still_succeeds(self):
        self.assertTrue(self._call(_response(404, {"message": "Unknown"}), discord_helper.delete_scheduled_event, "g1", "e1"))


if __name__ == "__main__":
    unittest.main()
