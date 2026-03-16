import unittest
from unittest.mock import Mock, patch

from commands.models.response_message import ResponseMessage
from commands.register.register_commands import register_user, register_remove
from database.models.event_data import EventData


def _make_event_item(registered=None, register_enabled=True):
    return {
        EventData.Keys.REGISTERED: registered if registered is not None else {},
        EventData.Keys.CHECKED_IN: {},
        EventData.Keys.QUEUE: {},
        EventData.Keys.PARTICIPANT_ROLE: "",
        EventData.Keys.CHECK_IN_ENABLED: False,
        EventData.Keys.REGISTER_ENABLED: register_enabled,
        EventData.Keys.START_MESSAGE: "",
        EventData.Keys.END_MESSAGE: "",
    }


def _make_aws(event_item=None):
    aws = Mock()
    aws.dynamodb_table.get_item.return_value = (
        {"Item": event_item} if event_item is not None else {}
    )
    return aws


def _make_event(user_id="U1", username="Tester", server_id="S1", event_name="evt-1", target_user=None):
    event = Mock()
    event.get_server_id.return_value = server_id
    event.get_user_id.return_value = user_id
    event.get_username.return_value = username

    def get_command_input_value(key):
        values = {"event_name": event_name, "user": target_user}
        return values.get(key)

    event.get_command_input_value.side_effect = get_command_input_value
    return event


class TestRegisterUser(unittest.TestCase):
    def test_event_not_found_returns_error(self):
        result = register_user(_make_event(), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_registration_closed_returns_error(self):
        item = _make_event_item(register_enabled=False)
        result = register_user(_make_event(), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not open", result.content)

    def test_already_registered_returns_info(self):
        participant = {
            "display_name": "Tester",
            "user_id": "U1",
            "time_added": "2026-01-01T00:00:00Z",
            "source": "manual",
        }
        item = _make_event_item(registered={"U1": participant})
        mock_existing = Mock()
        mock_existing.get_relative_time_added.return_value = "just now"
        with patch("commands.register.register_commands.RegisteredParticipant.from_dynamodb",
                   return_value=mock_existing):
            result = register_user(_make_event(user_id="U1"), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("already registered", result.content)

    def test_success_calls_update_and_returns_confirmation(self):
        item = _make_event_item(registered={}, register_enabled=True)
        aws = _make_aws(event_item=item)
        result = register_user(_make_event(user_id="U1"), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("registered", result.content.lower())
        aws.dynamodb_table.update_item.assert_called_once()


class TestRegisterRemove(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = register_remove(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = register_remove(_make_event(target_user="U2"), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_user_not_registered_returns_warning(self):
        item = _make_event_item(registered={})
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = register_remove(_make_event(target_user="U2"), _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not registered", result.content)

    def test_success_calls_update_and_returns_confirmation(self):
        participant = {
            "display_name": "Other",
            "user_id": "U2",
            "time_added": "2026-01-01T00:00:00Z",
            "source": "manual",
        }
        item = _make_event_item(registered={"U2": participant})
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = register_remove(_make_event(target_user="U2"), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("removed", result.content.lower())
        aws.dynamodb_table.update_item.assert_called_once()


if __name__ == "__main__":
    unittest.main()
