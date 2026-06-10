import unittest
from unittest.mock import Mock, patch

from commands.check_in.check_in_commands import remove_checked_in, show_not_checked_in
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def _make_event_data(checked_in=None, participant_role=None, registered=None, startgg_url=None):
    return EventData(
        checked_in=checked_in if checked_in is not None else {},
        registered=registered if registered is not None else {},
        queue={},
        participant_role=participant_role,
        check_in_enabled=True,
        register_enabled=True,
        start_message="",
        end_message="",
        startgg_url=startgg_url,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = kwargs.get("server_id", "server123")
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    inputs = kwargs.get("inputs", {})
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    aws.remove_role_sqs_queue = Mock()
    return aws


class TestRemoveCheckedIn(unittest.TestCase):
    @patch("commands.check_in.check_in_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = remove_checked_in(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no permission", result.content)

    @patch("commands.check_in.check_in_commands.permissions_helper")
    @patch("commands.check_in.check_in_commands.db_helper")
    def test_user_not_checked_in_returns_warning(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(checked_in={})
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event1", "user": "user_xyz"})

        result = remove_checked_in(event, aws)

        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not checked in", result.content)
        aws.dynamodb_table.update_item.assert_not_called()

    @patch("commands.check_in.check_in_commands.permissions_helper")
    @patch("commands.check_in.check_in_commands.db_helper")
    def test_removes_user_from_checked_in(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            checked_in={"user_xyz": {"display_name": "Bob", "user_id": "user_xyz", "time_added": "2025-01-01T00:00:00"}}
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event1", "user": "user_xyz"})

        result = remove_checked_in(event, aws)

        self.assertIsInstance(result, ResponseMessage)
        aws.dynamodb_table.update_item.assert_called_once()
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertIn("REMOVE", call_kwargs["UpdateExpression"])
        self.assertEqual(call_kwargs["ExpressionAttributeNames"]["#uid"], "user_xyz")

    @patch("commands.check_in.check_in_commands.permissions_helper")
    @patch("commands.check_in.check_in_commands.db_helper")
    def test_no_participant_role_skips_role_removal_queue(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            checked_in={"user_xyz": {"display_name": "Bob", "user_id": "user_xyz", "time_added": "2025-01-01T00:00:00"}},
            participant_role=None,
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event1", "user": "user_xyz"})

        remove_checked_in(event, aws)

        aws.remove_role_sqs_queue.send_messages.assert_not_called()

    @patch("commands.check_in.check_in_commands.permissions_helper")
    @patch("commands.check_in.check_in_commands.db_helper")
    def test_participant_role_set_queues_role_removal(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            checked_in={"user_xyz": {"display_name": "Bob", "user_id": "user_xyz", "time_added": "2025-01-01T00:00:00"}},
            participant_role="role_999",
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "event1", "user": "user_xyz"})

        result = remove_checked_in(event, aws)

        aws.remove_role_sqs_queue.send_messages.assert_called_once()
        self.assertIn("role removal", result.content)


class TestShowNotCheckedIn(unittest.TestCase):
    _REGISTERED = {"u1": {"display_name": "Alice", "user_id": "u1", "time_added": "2025-01-01T00:00:00"}}

    @patch("commands.check_in.check_in_commands.message_helper")
    @patch("commands.check_in.check_in_commands.event_commands")
    @patch("commands.check_in.check_in_commands.db_helper")
    @patch("commands.check_in.check_in_commands.permissions_helper")
    def test_non_startgg_event_does_not_refresh(self, mock_perms, mock_db, mock_event_commands, mock_msg):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(registered=self._REGISTERED)
        mock_msg.build_participants_list.return_value = "ABSENT_LIST"
        event = _make_event(inputs={"event_name": "event1"})

        result = show_not_checked_in(event, _make_aws())

        mock_event_commands.refresh_event_from_startgg.assert_not_called()
        self.assertIn("ABSENT_LIST", result.content)
        self.assertNotIn("refreshed from start.gg", result.content)

    @patch("commands.check_in.check_in_commands.message_helper")
    @patch("commands.check_in.check_in_commands.event_commands")
    @patch("commands.check_in.check_in_commands.db_helper")
    @patch("commands.check_in.check_in_commands.permissions_helper")
    def test_startgg_event_refreshes_and_prepends_summary(self, mock_perms, mock_db, mock_event_commands, mock_msg):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            registered=self._REGISTERED, startgg_url="https://start.gg/x"
        )
        mock_msg.build_participants_list.return_value = "ABSENT_LIST"
        summary = "👍 Event refreshed from start.gg:\n• 👥 Registered list updated with 46 participant(s)"
        mock_event_commands.refresh_event_from_startgg.return_value = summary
        event = _make_event(inputs={"event_name": "event1"})

        result = show_not_checked_in(event, _make_aws())

        mock_event_commands.refresh_event_from_startgg.assert_called_once()
        # Re-fetches event data after refresh so the absent list uses the latest registrants.
        self.assertEqual(mock_db.get_server_event_data_or_fail.call_count, 2)
        self.assertTrue(result.content.startswith(summary))
        self.assertIn("ABSENT_LIST", result.content)

    @patch("commands.check_in.check_in_commands.message_helper")
    @patch("commands.check_in.check_in_commands.event_commands")
    @patch("commands.check_in.check_in_commands.db_helper")
    @patch("commands.check_in.check_in_commands.permissions_helper")
    def test_startgg_refresh_failure_falls_back_to_saved_list(self, mock_perms, mock_db, mock_event_commands, mock_msg):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            registered=self._REGISTERED, startgg_url="https://start.gg/x"
        )
        mock_msg.build_participants_list.return_value = "ABSENT_LIST"
        mock_event_commands.refresh_event_from_startgg.side_effect = RuntimeError("start.gg down")
        event = _make_event(inputs={"event_name": "event1"})

        result = show_not_checked_in(event, _make_aws())

        self.assertIn("Could not refresh from start.gg", result.content)
        self.assertIn("ABSENT_LIST", result.content)


if __name__ == "__main__":
    unittest.main()
