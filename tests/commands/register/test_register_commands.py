import unittest
from unittest.mock import Mock, patch

import commands.register.register_commands as register_commands
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def _make_event_data(registered=None, register_enabled=True, event_id="event_111"):
    return EventData(
        checked_in={},
        registered=registered if registered is not None else {},
        queue={},
        participant_role=None,
        check_in_enabled=False,
        register_enabled=register_enabled,
        start_message="",
        end_message="",
        event_id=event_id,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = kwargs.get("server_id", "server123")
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    event.get_username.return_value = kwargs.get("username", "TestUser")
    event.event_body = kwargs.get("event_body", {})
    inputs = kwargs.get("inputs", {})
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    return aws


class TestToggleRegister(unittest.TestCase):
    @patch("commands.register.register_commands.permissions_helper")
    def test_missing_organizer_role_returns_error_without_db_write(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        aws = _make_aws()
        result = register_commands.toggle_register(_make_event(), aws)
        self.assertIn("no permission", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.register.register_commands.permissions_helper")
    @patch("commands.register.register_commands.db_helper")
    def test_event_lookup_failure_is_propagated(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = ResponseMessage(content="event not found")
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "missing", "state": "Start"})

        result = register_commands.toggle_register(event, aws)

        self.assertIn("event not found", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.register.register_commands.permissions_helper")
    @patch("commands.register.register_commands.db_helper")
    def test_start_state_enables_registration(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data()
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111", "state": "Start"})

        result = register_commands.toggle_register(event, aws)

        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":enable"], True)
        self.assertIn("register_enabled", call_kwargs["UpdateExpression"])
        self.assertEqual(call_kwargs["Key"]["SK"], "EVENT#event_111")
        self.assertIn("Registration started", result.content)

    @patch("commands.register.register_commands.permissions_helper")
    @patch("commands.register.register_commands.db_helper")
    def test_end_state_disables_registration(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data()
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111", "state": "End"})

        result = register_commands.toggle_register(event, aws)

        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":enable"], False)
        self.assertIn("Registration closed", result.content)


class TestRegisterUser(unittest.TestCase):
    @patch("commands.register.register_commands.db_helper")
    def test_happy_path_self_registration_writes_participant(self, mock_db):
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(register_enabled=True)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111"}, user_id="user_abc", username="TestUser")

        result = register_commands.register_user(event, aws)

        self.assertIn("You have been registered", result.content)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn("SET registered.#uid", call_kwargs["UpdateExpression"])
        self.assertEqual(call_kwargs["ExpressionAttributeNames"]["#uid"], "user_abc")
        participant_info = call_kwargs["ExpressionAttributeValues"][":participant_info"]
        self.assertEqual(participant_info["display_name"], "TestUser")
        self.assertEqual(participant_info["user_id"], "user_abc")
        self.assertEqual(participant_info["source"], "manual")

    @patch("commands.register.register_commands.db_helper")
    def test_closed_registration_rejects_self_registration_without_db_write(self, mock_db):
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(register_enabled=False)
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111"})

        result = register_commands.register_user(event, aws)

        self.assertIn("Registration is not open", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.register.register_commands.db_helper")
    def test_already_registered_user_gets_friendly_notice(self, mock_db):
        # register_user calls RegisteredParticipant.from_dynamodb on the stored record
        # and returns the friendly "already registered (X ago)" notice without writing.
        registered = {
            "user_abc": {
                "display_name": "TestUser",
                "user_id": "user_abc",
                "time_added": "2025-01-01T00:00:00Z",
                "source": "manual",
            }
        }
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(registered=registered)
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111"}, user_id="user_abc")

        result = register_commands.register_user(event, aws)

        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("already registered", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.register.register_commands.permissions_helper")
    def test_registering_target_user_without_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event_111", "user": "user_target"})

        result = register_commands.register_user(event, aws)

        self.assertIn("no permission", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.register.register_commands.permissions_helper")
    @patch("commands.register.register_commands.db_helper")
    def test_organizer_can_register_target_even_when_registration_closed(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(register_enabled=False)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event_body = {
            "data": {"resolved": {"users": {"user_target": {"global_name": "TargetUser", "username": "target"}}}}
        }
        event = _make_event(inputs={"event_name": "event_111", "user": "user_target"}, event_body=event_body)

        result = register_commands.register_user(event, aws)

        self.assertIn("has been registered", result.content)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["ExpressionAttributeNames"]["#uid"], "user_target")
        participant_info = call_kwargs["ExpressionAttributeValues"][":participant_info"]
        self.assertEqual(participant_info["display_name"], "TargetUser")


if __name__ == "__main__":
    unittest.main()
