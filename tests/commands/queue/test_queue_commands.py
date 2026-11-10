import unittest
from unittest.mock import Mock, patch

import commands.queue.queue_commands as queue_commands
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData

_KEY = {"PK": "SERVER#server123", "SK": "EVENT#event_111"}


def _entry(joined_at):
    return {"display_name": "X", "joined_at": joined_at}


def _make_event_data(queue=None, queue_enabled=True):
    return EventData(
        checked_in={},
        registered={},
        queue=queue if queue is not None else {},
        participant_role=None,
        check_in_enabled=False,
        register_enabled=False,
        start_message="",
        end_message="",
        event_id="event_111",
        event_name="Stream Night",
        queue_enabled=queue_enabled,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = "server123"
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    event.get_username.return_value = kwargs.get("username", "TestUser")
    inputs = {"event_name": "event_111", **kwargs.get("inputs", {})}
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    return aws


def _patch_db(mock_db, event_data):
    mock_db.get_server_event_data_or_fail.return_value = event_data
    mock_db.build_event_key.return_value = _KEY


@patch("commands.queue.queue_commands.queue_helper")
@patch("commands.queue.queue_commands.db_helper")
class TestJoinQueue(unittest.TestCase):
    def test_join_reports_position_and_length(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(queue={"other": _entry(1)}))
        mock_helper.get_position.side_effect = [None, 2]
        mock_helper.join_queue.return_value = {"other": _entry(1), "user_abc": _entry(2)}

        result = queue_commands.join_queue(_make_event(), _make_aws())

        self.assertEqual(mock_helper.join_queue.call_args.args[2:], ("user_abc", "TestUser"))
        self.assertIn("**#2** of 2", result.content)

    def test_repeat_join_reports_existing_spot_without_writing(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(queue={"user_abc": _entry(1)}))
        mock_helper.get_position.return_value = 1

        result = queue_commands.join_queue(_make_event(), _make_aws())

        self.assertIn("already **#1**", result.content)
        mock_helper.join_queue.assert_not_called()

    def test_rejected_while_closed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(queue_enabled=False))
        mock_helper.get_position.return_value = None

        result = queue_commands.join_queue(_make_event(), _make_aws())

        self.assertIn("closed", result.content)
        mock_helper.join_queue.assert_not_called()

    def test_double_submitted_join_reports_already_in(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())
        mock_helper.get_position.return_value = None
        mock_helper.join_queue.return_value = None

        result = queue_commands.join_queue(_make_event(), _make_aws())

        self.assertIn("already in", result.content)

    def test_event_lookup_error_is_returned(self, mock_db, mock_helper):
        mock_db.get_server_event_data_or_fail.return_value = ResponseMessage(content="no event")
        self.assertEqual(queue_commands.join_queue(_make_event(), _make_aws()).content, "no event")


@patch("commands.queue.queue_commands.queue_helper")
@patch("commands.queue.queue_commands.db_helper")
class TestLeaveQueue(unittest.TestCase):
    def test_leave_removes_caller_even_while_closed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(queue={"user_abc": _entry(1)}, queue_enabled=False))
        mock_helper.remove_from_queue.return_value = True

        result = queue_commands.leave_queue(_make_event(), _make_aws())

        self.assertEqual(mock_helper.remove_from_queue.call_args.args[2], "user_abc")
        self.assertIn("left", result.content)

    def test_leave_when_not_in_queue(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())

        result = queue_commands.leave_queue(_make_event(), _make_aws())

        self.assertIn("not in", result.content)
        mock_helper.remove_from_queue.assert_not_called()


@patch("commands.queue.queue_commands.permissions_helper")
@patch("commands.queue.queue_commands.db_helper")
class TestViewQueue(unittest.TestCase):
    def test_view_is_silent_by_default_and_shows_length(self, mock_db, mock_perms):
        _patch_db(mock_db, _make_event_data(queue={"u1": _entry(1), "u2": _entry(2)}))

        result = queue_commands.view_queue(_make_event(), _make_aws())

        self.assertIn("2 in queue", result.content)
        self.assertIn("<@u1>", result.content)
        self.assertEqual(result.allowed_mentions, {"parse": []})
        mock_perms.verify_has_organizer_role.assert_not_called()

    def test_ping_users_pings_when_organizer(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue={"u1": _entry(1)}))

        result = queue_commands.view_queue(_make_event(inputs={"ping_users": True}), _make_aws())

        self.assertIsNone(result.allowed_mentions)

    def test_ping_users_requires_organizer(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")

        result = queue_commands.view_queue(_make_event(inputs={"ping_users": True}), _make_aws())

        self.assertEqual(result.content, "no permission")
        mock_db.get_server_event_data_or_fail.assert_not_called()

    def test_empty_queue(self, mock_db, mock_perms):
        _patch_db(mock_db, _make_event_data(queue_enabled=False))
        result = queue_commands.view_queue(_make_event(), _make_aws())
        self.assertIn("empty", result.content)
        self.assertIn("closed", result.content)


@patch("commands.queue.queue_commands.queue_helper")
@patch("commands.queue.queue_commands.db_helper")
@patch("commands.queue.queue_commands.permissions_helper")
class TestOrganizerCommands(unittest.TestCase):
    def test_organizer_commands_require_organizer_role(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        aws = _make_aws()
        event = _make_event(inputs={"user": "target", "state": "Start"})

        for command in (
            queue_commands.toggle_queue,
            queue_commands.pop_queue,
            queue_commands.remove_from_queue,
            queue_commands.clear_queue,
        ):
            self.assertIn("no permission", command(event, aws).content)

        mock_db.get_server_event_data_or_fail.assert_not_called()
        aws.dynamodb_table.update_item.assert_not_called()
        mock_helper.pop_queue.assert_not_called()
        mock_helper.remove_from_queue.assert_not_called()
        mock_helper.clear_queue.assert_not_called()

    def test_toggle_start_opens_and_end_closes(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue_enabled=False))

        for state, expected in (("Start", True), ("End", False)):
            aws = _make_aws()
            queue_commands.toggle_queue(_make_event(inputs={"state": state}), aws)
            values = aws.dynamodb_table.update_item.call_args.kwargs["ExpressionAttributeValues"]
            self.assertEqual(values, {":enable": expected})

    def test_pop_pings_popped_users_and_reports_remaining(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue={"u1": _entry(1), "u2": _entry(2), "u3": _entry(3)}))
        mock_helper.pop_queue.return_value = ["u1", "u2"]

        result = queue_commands.pop_queue(_make_event(inputs={"count": 2}), _make_aws())

        self.assertEqual(mock_helper.pop_queue.call_args.args[3], 2)
        self.assertIn("<@u1>, <@u2>", result.content)
        self.assertIn("1 left", result.content)
        self.assertIsNone(result.allowed_mentions)  # real ping: they're up

    def test_pop_defaults_to_one(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue={"u1": _entry(1)}))
        mock_helper.pop_queue.return_value = ["u1"]

        queue_commands.pop_queue(_make_event(), _make_aws())

        self.assertEqual(mock_helper.pop_queue.call_args.args[3], 1)

    def test_pop_rejects_out_of_range_count(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        for count in (0, 11):
            result = queue_commands.pop_queue(_make_event(inputs={"count": count}), _make_aws())
            self.assertIn("between 1 and 10", result.content)
        mock_helper.pop_queue.assert_not_called()

    def test_pop_empty_queue(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data())
        result = queue_commands.pop_queue(_make_event(), _make_aws())
        self.assertIn("empty", result.content)
        mock_helper.pop_queue.assert_not_called()

    def test_remove_user(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue={"target": _entry(1)}))
        mock_helper.remove_from_queue.return_value = True

        result = queue_commands.remove_from_queue(_make_event(inputs={"user": "target"}), _make_aws())

        self.assertEqual(mock_helper.remove_from_queue.call_args.args[2], "target")
        self.assertIn("Removed <@target>", result.content)

    def test_remove_user_not_in_queue(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data())

        result = queue_commands.remove_from_queue(_make_event(inputs={"user": "target"}), _make_aws())

        self.assertIn("not in the queue", result.content)
        mock_helper.remove_from_queue.assert_not_called()

    def test_clear(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(queue={"u1": _entry(1)}))

        result = queue_commands.clear_queue(_make_event(), _make_aws())

        mock_helper.clear_queue.assert_called_once()
        self.assertIn("cleared", result.content)
