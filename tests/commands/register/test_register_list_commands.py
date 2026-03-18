import unittest
from unittest.mock import Mock, patch

from commands.models.response_message import ResponseMessage
from commands.register.register_list_commands import show_registered, clear_registered
from database.models.event_data import EventData


def _make_event_item(registered=None):
    return {
        EventData.Keys.REGISTERED: registered if registered is not None else {},
        EventData.Keys.CHECKED_IN: {},
        EventData.Keys.QUEUE: {},
        EventData.Keys.PARTICIPANT_ROLE: "",
        EventData.Keys.CHECK_IN_ENABLED: False,
        EventData.Keys.REGISTER_ENABLED: True,
        EventData.Keys.START_MESSAGE: "",
        EventData.Keys.END_MESSAGE: "",
    }


def _make_aws(event_item=None):
    aws = Mock()
    aws.dynamodb_table.get_item.return_value = (
        {"Item": event_item} if event_item is not None else {}
    )
    return aws


def _make_event(server_id="S1", event_name="evt-1"):
    event = Mock()
    event.get_server_id.return_value = server_id
    event.get_command_input_value.return_value = event_name
    return event


class TestShowRegistered(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = show_registered(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = show_registered(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_no_registered_users_returns_info(self):
        item = _make_event_item(registered={})
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = show_registered(_make_event(), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no registered", result.content.lower())

    def test_registered_users_returned_in_list(self):
        participant = {
            "display_name": "PlayerOne",
            "user_id": "U1",
            "time_added": "2026-01-01T00:00:00Z",
            "source": "manual",
        }
        item = _make_event_item(registered={"U1": participant})
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = show_registered(_make_event(), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Registered Users", result.content)


class TestClearRegistered(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = clear_registered(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = clear_registered(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_no_registered_users_returns_info(self):
        item = _make_event_item(registered={})
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = clear_registered(_make_event(), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no registered", result.content.lower())

    def test_success_clears_all_and_returns_confirmation(self):
        participant = {
            "display_name": "PlayerOne",
            "user_id": "U1",
            "time_added": "2026-01-01T00:00:00Z",
            "source": "manual",
        }
        item = _make_event_item(registered={"U1": participant})
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = clear_registered(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("cleared", result.content.lower())
        aws.dynamodb_table.update_item.assert_called_once()


if __name__ == "__main__":
    unittest.main()
