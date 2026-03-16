import unittest
from unittest.mock import Mock, patch

from commands.models.response_message import ResponseMessage
from commands.event.event_commands import create_event_startgg, event_refresh_startgg, events_list
from commands.event.startgg.models.startgg_event import StartggEvent
from database.models.registered_participant import RegisteredParticipant
from database.models.participant import Participant


VALID_URL = "https://www.start.gg/tournament/midweek-melting/event/main-bracket"
INVALID_URL = "https://bad-url.com/not-startgg"


def _make_aws():
    aws = Mock()
    aws.dynamodb_table.get_item.return_value = {}
    return aws


def _make_event(server_id="S1", event_name="evt-1", event_link=VALID_URL):
    event = Mock()
    event.get_server_id.return_value = server_id

    def get_command_input_value(key):
        return {"event_name": event_name, "event_link": event_link}.get(key)

    event.get_command_input_value.side_effect = get_command_input_value
    return event


def _make_startgg_event(
    event_name="Main Bracket",
    start_time_utc="2026-03-01T18:00:00Z",
    end_time_utc="2026-03-01T22:00:00Z",
    location="Venue Hall",
    participants=None,
    no_discord_participants=None,
):
    return StartggEvent(
        tourney_name="Midweek Melting",
        event_name=event_name,
        start_time_utc=start_time_utc,
        end_time_utc=end_time_utc,
        location=location,
        participants=participants or [],
        no_discord_participants=no_discord_participants or [],
    )


class TestCreateEventStartgg(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_invalid_url_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = create_event_startgg(_make_event(event_link=INVALID_URL), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not valid", result.content)

    def test_missing_times_returns_error(self):
        startgg_event = _make_startgg_event(start_time_utc=None, end_time_utc=None)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("start/end times", result.content)

    def test_success_no_participants(self):
        startgg_event = _make_startgg_event()
        aws = _make_aws()
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Main Bracket", result.content)
        self.assertIn("0 registered", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    def test_success_with_participants_updates_registered(self):
        participants = [
            RegisteredParticipant(display_name="Player1", user_id="U1", source="startgg"),
        ]
        startgg_event = _make_startgg_event(participants=participants)
        aws = _make_aws()
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("1 registered", result.content)
        aws.dynamodb_table.update_item.assert_called_once()

    def test_success_includes_no_discord_report(self):
        no_discord = [Participant(display_name="NoDiscordGuy", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event), \
             patch("commands.event.event_commands.create_event_record", return_value="EVT1"):
            result = create_event_startgg(_make_event(), _make_aws())
        self.assertIn("NoDiscordGuy", result.content)
        self.assertIn("do not have Discord linked", result.content)


class TestEventRefreshStartgg(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = event_refresh_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_invalid_url_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = event_refresh_startgg(_make_event(event_link=INVALID_URL), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not valid", result.content)

    def test_no_participants_returns_error(self):
        startgg_event = _make_startgg_event(participants=[], no_discord_participants=[])
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("No registered participants", result.content)

    def test_success_with_participants_updates_registered(self):
        participants = [
            RegisteredParticipant(display_name="Player1", user_id="U1", source="startgg"),
            RegisteredParticipant(display_name="Player2", user_id="U2", source="startgg"),
        ]
        startgg_event = _make_startgg_event(participants=participants)
        aws = _make_aws()
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("2 participants", result.content)
        aws.dynamodb_table.update_item.assert_called_once()

    def test_success_includes_no_discord_report(self):
        no_discord = [Participant(display_name="OffGridPlayer", user_id=Participant.DEFAULT_ID_PLACEHOLDER)]
        startgg_event = _make_startgg_event(no_discord_participants=no_discord)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None), \
             patch("commands.event.startgg.startgg_api.is_valid_startgg_url", return_value=True), \
             patch("commands.event.startgg.startgg_api.query_startgg_event", return_value=startgg_event):
            result = event_refresh_startgg(_make_event(), _make_aws())
        self.assertIn("OffGridPlayer", result.content)


class TestEventsList(unittest.TestCase):
    def test_no_events_returns_info(self):
        aws = _make_aws()
        with patch("database.dynamodb_utils.get_events_for_server", return_value=[]):
            result = events_list(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("No events", result.content)

    def test_events_listed_with_names(self):
        aws = _make_aws()
        mock_events = [("Summer Smash", "EVT1"), ("Winter Bout", "EVT2")]
        with patch("database.dynamodb_utils.get_events_for_server", return_value=mock_events):
            result = events_list(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Summer Smash", result.content)
        self.assertIn("Winter Bout", result.content)


if __name__ == "__main__":
    unittest.main()
