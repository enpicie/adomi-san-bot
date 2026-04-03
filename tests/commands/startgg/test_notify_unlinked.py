import unittest
from unittest.mock import Mock, patch

from commands.startgg.startgg_commands import notify_unlinked
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = kwargs.get("server_id", "server123")
    inputs = kwargs.get("inputs", {})
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    return aws


def _make_event_data(startgg_url="https://start.gg/tournament/test/event/bracket", registered=None):
    data = Mock(spec=EventData)
    data.startgg_url = startgg_url
    data.registered = registered if registered is not None else {}
    return data


def _make_participant(display_name):
    p = Mock()
    p.display_name = display_name
    return p


class TestNotifyUnlinked(unittest.TestCase):
    @patch("commands.startgg.startgg_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = notify_unlinked(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no permission", result.content)

    @patch("commands.startgg.startgg_commands.permissions_helper")
    @patch("commands.startgg.startgg_commands.db_helper")
    def test_event_not_linked_to_startgg_returns_error(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(startgg_url=None)
        event = _make_event(inputs={"event_name": "evt1"})
        result = notify_unlinked(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not linked", result.content)

    @patch("commands.startgg.startgg_commands.permissions_helper")
    @patch("commands.startgg.startgg_commands.db_helper")
    def test_db_lookup_failure_propagates(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = ResponseMessage(content="event not found")
        event = _make_event(inputs={"event_name": "missing"})
        result = notify_unlinked(event, _make_aws())
        self.assertIn("event not found", result.content)

    @patch("commands.startgg.startgg_commands.permissions_helper")
    @patch("commands.startgg.startgg_commands.db_helper")
    @patch("commands.startgg.startgg_commands.startgg_api")
    def test_all_linked_returns_success_message(self, mock_api, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data()
        mock_api.query_startgg_event.return_value.participants = []
        mock_api.query_startgg_event.return_value.no_discord_participants = []
        event = _make_event(inputs={"event_name": "evt1"})
        result = notify_unlinked(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("All start.gg participants", result.content)

    @patch("commands.startgg.startgg_commands.permissions_helper")
    @patch("commands.startgg.startgg_commands.db_helper")
    @patch("commands.startgg.startgg_commands.startgg_api")
    def test_unlinked_participants_listed_in_response(self, mock_api, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data()
        mock_api.query_startgg_event.return_value.participants = []
        mock_api.query_startgg_event.return_value.no_discord_participants = [
            _make_participant("PlayerOne"),
            _make_participant("PlayerTwo"),
        ]
        event = _make_event(inputs={"event_name": "evt1"})
        result = notify_unlinked(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("PlayerOne", result.content)
        self.assertIn("PlayerTwo", result.content)
        self.assertIn("2", result.content)

    @patch("commands.startgg.startgg_commands.permissions_helper")
    @patch("commands.startgg.startgg_commands.db_helper")
    @patch("commands.startgg.startgg_commands.startgg_api")
    def test_startgg_api_failure_returns_error(self, mock_api, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data()
        mock_api.query_startgg_event.side_effect = Exception("network error")
        event = _make_event(inputs={"event_name": "evt1"})
        result = notify_unlinked(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Failed to fetch", result.content)


if __name__ == "__main__":
    unittest.main()
