import unittest
from unittest.mock import Mock, patch

from commands.models.response_message import ResponseMessage
from commands.register.register_commands import register_user, register_remove, toggle_register
from commands.register.register_constants import START_PARAM, END_PARAM
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


def _make_event(user_id="U1", username="Tester", server_id="S1", event_name="evt-1",
                target_user=None, state=None, resolved_users=None):
    event = Mock()
    event.get_server_id.return_value = server_id
    event.get_user_id.return_value = user_id
    event.get_username.return_value = username
    event.event_body = {
        "data": {
            "resolved": {"users": resolved_users or {}}
        }
    }

    def get_command_input_value(key):
        values = {"event_name": event_name, "user": target_user, "state": state}
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

    def test_organizer_registers_target_user_success(self):
        item = _make_event_item(registered={}, register_enabled=True)
        aws = _make_aws(event_item=item)
        resolved = {"U2": {"global_name": "TargetUser", "username": "targetuser"}}
        event = _make_event(user_id="U1", target_user="U2", resolved_users=resolved)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = register_user(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("registered", result.content.lower())
        aws.dynamodb_table.update_item.assert_called_once()

    def test_organizer_registers_target_user_no_permission(self):
        item = _make_event_item(registered={}, register_enabled=True)
        event = _make_event(user_id="U1", target_user="U2")
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = register_user(event, _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_organizer_registers_already_registered_target_user(self):
        participant = {
            "display_name": "Other",
            "user_id": "U2",
            "time_added": "2026-01-01T00:00:00Z",
            "source": "manual",
        }
        item = _make_event_item(registered={"U2": participant})
        mock_existing = Mock()
        mock_existing.get_relative_time_added.return_value = "5 minutes ago"
        event = _make_event(user_id="U1", target_user="U2")
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            with patch("commands.register.register_commands.RegisteredParticipant.from_dynamodb",
                       return_value=mock_existing):
                result = register_user(event, _make_aws(event_item=item))
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("already registered", result.content)

    def test_organizer_registers_uses_global_name_fallback_to_username(self):
        item = _make_event_item(registered={}, register_enabled=True)
        aws = _make_aws(event_item=item)
        resolved = {"U2": {"username": "fallbackname"}}  # no global_name
        event = _make_event(user_id="U1", target_user="U2", resolved_users=resolved)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            register_user(event, aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args[1]
        participant_info = call_kwargs["ExpressionAttributeValues"][":participant_info"]
        self.assertEqual(participant_info["display_name"], "fallbackname")


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


class TestToggleRegister(unittest.TestCase):
    def test_no_organizer_role_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role",
                   return_value=ResponseMessage(content="no permission")):
            result = toggle_register(_make_event(state=START_PARAM), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertEqual(result.content, "no permission")

    def test_event_not_found_returns_error(self):
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = toggle_register(_make_event(state=START_PARAM), _make_aws(event_item=None))
        self.assertIsInstance(result, ResponseMessage)

    def test_start_enables_registration(self):
        item = _make_event_item(register_enabled=False)
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = toggle_register(_make_event(state=START_PARAM), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("started", result.content.lower())
        call_kwargs = aws.dynamodb_table.update_item.call_args[1]
        self.assertTrue(call_kwargs["ExpressionAttributeValues"][":enable"])

    def test_end_disables_registration(self):
        item = _make_event_item(register_enabled=True)
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            result = toggle_register(_make_event(state=END_PARAM), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("closed", result.content.lower())
        call_kwargs = aws.dynamodb_table.update_item.call_args[1]
        self.assertFalse(call_kwargs["ExpressionAttributeValues"][":enable"])

    def test_calls_update_item(self):
        item = _make_event_item()
        aws = _make_aws(event_item=item)
        with patch("utils.permissions_helper.verify_has_organizer_role", return_value=None):
            toggle_register(_make_event(state=START_PARAM), aws)
        aws.dynamodb_table.update_item.assert_called_once()


if __name__ == "__main__":
    unittest.main()
