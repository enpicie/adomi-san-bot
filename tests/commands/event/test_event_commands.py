import unittest
from unittest.mock import Mock, patch

import commands.event.event_commands as event_commands
from database.models.event_data import EventData


def _make_event_data(participant_role=None, checked_in=None, event_id="event_111", event_name="Weekly Bracket"):
    return EventData(
        checked_in=checked_in if checked_in is not None else {},
        registered={},
        queue={},
        participant_role=participant_role,
        check_in_enabled=False,
        register_enabled=True,
        start_message="",
        end_message="",
        event_id=event_id,
        event_name=event_name,
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


def _make_server_config():
    config = Mock()
    config.default_participant_role = None
    config.should_always_remind = False
    return config


class TestDeleteEvent(unittest.TestCase):
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.queue_role_removal")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_role_and_checked_in_users_enqueues_removal_for_those_users(
        self, mock_perms, mock_db, mock_queue, mock_event_helper, mock_schedule
    ):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            participant_role="role_999",
            checked_in={
                "user_a": {"display_name": "A", "user_id": "user_a"},
                "user_b": {"display_name": "B", "user_id": "user_b"},
            },
        )
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        result = event_commands.delete_event(event, aws)

        # The checked-in users have their participant role queued for removal before deletion.
        mock_queue.enqueue_remove_role_jobs.assert_called_once()
        call_kwargs = mock_queue.enqueue_remove_role_jobs.call_args.kwargs
        self.assertEqual(set(call_kwargs["user_ids"]), {"user_a", "user_b"})
        self.assertEqual(call_kwargs["role_id"], "role_999")
        self.assertIs(call_kwargs["sqs_queue"], aws.remove_role_sqs_queue)
        # Record is still deleted and the user is told removals were queued.
        mock_event_helper.delete_event_record.assert_called_once()
        self.assertIn("queued", result.content)

    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.queue_role_removal")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_no_participant_role_does_not_enqueue_removal(
        self, mock_perms, mock_db, mock_queue, mock_event_helper, mock_schedule
    ):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            participant_role=None,
            checked_in={"user_a": {"display_name": "A", "user_id": "user_a"}},
        )
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        result = event_commands.delete_event(event, aws)

        mock_queue.enqueue_remove_role_jobs.assert_not_called()
        mock_event_helper.delete_event_record.assert_called_once()
        self.assertNotIn("queued", result.content)

    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.queue_role_removal")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_role_set_but_no_checked_in_users_does_not_enqueue_removal(
        self, mock_perms, mock_db, mock_queue, mock_event_helper, mock_schedule
    ):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(
            participant_role="role_999",
            checked_in={},
        )
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        result = event_commands.delete_event(event, aws)

        mock_queue.enqueue_remove_role_jobs.assert_not_called()
        mock_event_helper.delete_event_record.assert_called_once()
        self.assertNotIn("queued", result.content)


def _make_startgg_event(event_name="Start.gg Bracket"):
    startgg_event = Mock()
    startgg_event.event_name = event_name
    startgg_event.start_time_utc = "2099-01-01T12:00:00Z"  # far future, never "past"
    startgg_event.location = "Online"
    startgg_event.participants = []
    startgg_event.no_discord_participants = []
    return startgg_event


class TestCreateEventStartgg(unittest.TestCase):
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_uses_provided_event_name_when_given(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_tz, mock_schedule
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_api.query_startgg_event.return_value = _make_startgg_event(event_name="Start.gg Name")
        mock_tz.to_utc_iso.return_value = "2099-01-01T14:00:00Z"
        mock_event_helper.create_event_record.return_value = "new_event_id"
        aws = _make_aws()
        event = _make_event(inputs={
            "event_link": "https://start.gg/x",
            "event_name": "Custom Override Name",
        })

        result = event_commands.create_event_startgg(event, aws)

        # Contract: the persisted record name is the user-provided override, not the start.gg name.
        record = mock_event_helper.create_event_record.call_args.kwargs["record"]
        self.assertEqual(record.name, "Custom Override Name")
        self.assertIn("Custom Override Name", result.content)
        self.assertNotIn("Start.gg Name", result.content)

    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_falls_back_to_startgg_name_when_input_absent(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_tz, mock_schedule
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_api.query_startgg_event.return_value = _make_startgg_event(event_name="Start.gg Name")
        mock_tz.to_utc_iso.return_value = "2099-01-01T14:00:00Z"
        mock_event_helper.create_event_record.return_value = "new_event_id"
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/x"})  # no event_name input

        result = event_commands.create_event_startgg(event, aws)

        # Contract: with no override, the persisted record name is the start.gg event name.
        record = mock_event_helper.create_event_record.call_args.kwargs["record"]
        self.assertEqual(record.name, "Start.gg Name")
        self.assertIn("Start.gg Name", result.content)


if __name__ == "__main__":
    unittest.main()
