import json
import unittest
from unittest.mock import Mock, patch

from commands.league.league_commands import (
    create_league, update_league, sync_active_participants,
    join_league, setup_league, toggle_join_league, toggle_report_score, LEAGUE_ID_MAX_LENGTH,
    deactivate_league_participant, report_score,
)
from commands.models.response_message import ResponseMessage
from database.models.league_data import LeagueData


def _make_league(
    league_id="TST",
    league_name="Test League",
    google_sheets_link="https://docs.google.com/spreadsheets/d/abc/edit",
    active_players=None,
    join_enabled=False,
    report_enabled=False,
    active_participant_role=None,
):
    return LeagueData(
        league_id=league_id,
        league_name=league_name,
        google_sheets_link=google_sheets_link,
        active_players=active_players or {},
        join_enabled=join_enabled,
        report_enabled=report_enabled,
        active_participant_role=active_participant_role,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = kwargs.get("server_id", "server123")
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    event.get_display_name.return_value = kwargs.get("display_name", "Alice")
    event.event_body = kwargs.get("event_body", {})
    inputs = kwargs.get("inputs", {})
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    aws.remove_role_sqs_queue = Mock()
    aws.sheets_agent_sqs_queue = Mock()
    return aws


def _get_dispatched_command(aws) -> str:
    """Extract the command_name from the SQS message sent to sheets_agent."""
    call_kwargs = aws.sheets_agent_sqs_queue.send_message.call_args.kwargs
    return json.loads(call_kwargs["MessageBody"])["command_name"]


class TestCreateLeague(unittest.TestCase):
    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_league_id_too_long_returns_error(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        aws = _make_aws()
        event = _make_event(inputs={
            "league_id": "TOOLONG",
            "league_name": "Test",
            "google_sheets_link": "https://...",
            "active_participant_role": None,
        })
        result = create_league(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn(str(LEAGUE_ID_MAX_LENGTH), result.content)
        aws.dynamodb_table.put_item.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_duplicate_league_id_returns_error(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league()
        aws = _make_aws()
        event = _make_event(inputs={
            "league_id": "TST",
            "league_name": "Test",
            "google_sheets_link": "https://...",
            "active_participant_role": None,
        })
        result = create_league(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("already exists", result.content)
        aws.dynamodb_table.put_item.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_success_calls_put_item(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = ResponseMessage(content="not found")
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={
            "league_id": "TST",
            "league_name": "Test League",
            "google_sheets_link": "https://docs.google.com/spreadsheets/d/abc/edit",
            "active_participant_role": None,
        })
        result = create_league(event, aws)
        aws.dynamodb_table.put_item.assert_called_once()
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("TST", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_active_participant_role_stored_as_raw_id(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = ResponseMessage(content="not found")
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={
            "league_id": "TST",
            "league_name": "Test League",
            "google_sheets_link": "https://docs.google.com/spreadsheets/d/abc/edit",
            "active_participant_role": "<@&role_999>",
        })
        create_league(event, aws)
        item_stored = aws.dynamodb_table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item_stored[LeagueData.Keys.ACTIVE_PARTICIPANT_ROLE], "role_999")

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = create_league(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("no permission", result.content)


class TestUpdateLeague(unittest.TestCase):
    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_no_fields_provided_returns_no_changes(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league()
        event = _make_event(inputs={"league_name": "TST", "new_name": None, "google_sheets_link": None, "active_participant_role": None})
        result = update_league(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("No changes", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_updating_name_calls_update_item(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league()
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "new_name": "New Name", "google_sheets_link": None, "active_participant_role": None})
        result = update_league(event, aws)
        aws.dynamodb_table.update_item.assert_called_once()
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("TST", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_role_mention_format_is_stripped_before_storing(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league()
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "new_name": None, "google_sheets_link": None, "active_participant_role": "<@&999888777>"})
        update_league(event, aws)
        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":active_participant_role"], "999888777")

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = update_league(_make_event(), _make_aws())
        self.assertIn("no permission", result.content)


class TestSetupLeague(unittest.TestCase):
    def test_dispatches_to_sheets_agent_and_returns_ack(self):
        aws = _make_aws()
        result = setup_league(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Setting up", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-setup")


class TestJoinLeague(unittest.TestCase):
    def test_dispatches_to_sheets_agent_and_returns_ack(self):
        aws = _make_aws()
        result = join_league(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Adding you", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-join")


class TestSyncActiveParticipants(unittest.TestCase):
    def test_dispatches_to_sheets_agent_and_returns_ack(self):
        aws = _make_aws()
        result = sync_active_participants(_make_event(), aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Syncing", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-sync-participants")


class TestToggleJoinLeague(unittest.TestCase):
    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_enables_join_when_state_is_start(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(join_enabled=False)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "state": "Start"})

        result = toggle_join_league(event, aws)

        update_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertTrue(update_kwargs["ExpressionAttributeValues"][":join_enabled"])
        self.assertIn("started", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_disables_join_when_state_is_not_start(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(join_enabled=True)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "state": "Stop"})

        result = toggle_join_league(event, aws)

        update_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertFalse(update_kwargs["ExpressionAttributeValues"][":join_enabled"])
        self.assertIn("closed", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = toggle_join_league(_make_event(), _make_aws())
        self.assertIn("no permission", result.content)


class TestReportScore(unittest.TestCase):
    @patch("commands.league.league_commands.db_helper")
    def test_dispatches_to_sheets_agent_when_report_enabled(self, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = _make_league(report_enabled=True)
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})
        result = report_score(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-report-score")

    @patch("commands.league.league_commands.db_helper")
    def test_returns_error_when_report_disabled(self, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = _make_league(report_enabled=False)
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})
        result = report_score(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("closed", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_not_called()

    @patch("commands.league.league_commands.db_helper")
    def test_returns_error_when_league_not_found(self, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = ResponseMessage(content="not found")
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})
        result = report_score(event, aws)
        self.assertIn("not found", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_not_called()


class TestToggleReportScore(unittest.TestCase):
    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_enables_reporting_when_state_is_start(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(report_enabled=False)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "state": "Start"})

        result = toggle_report_score(event, aws)

        update_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertTrue(update_kwargs["ExpressionAttributeValues"][":report_enabled"])
        self.assertIn("started", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    def test_disables_reporting_when_state_is_not_start(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(report_enabled=True)
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST", "state": "End"})

        result = toggle_report_score(event, aws)

        update_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertFalse(update_kwargs["ExpressionAttributeValues"][":report_enabled"])
        self.assertIn("closed", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = toggle_report_score(_make_event(), _make_aws())
        self.assertIn("no permission", result.content)


class TestDeactivateLeagueParticipant(unittest.TestCase):
    def test_dispatches_without_player_param_no_perm_check(self):
        aws = _make_aws()
        event = _make_event(inputs={"player": None})
        result = deactivate_league_participant(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-deactivate")

    @patch("commands.league.league_commands.permissions_helper")
    def test_player_param_requires_organizer_role(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        aws = _make_aws()
        event = _make_event(inputs={"player": "some_user"})
        result = deactivate_league_participant(event, aws)
        self.assertIn("organizers", result.content)
        aws.sheets_agent_sqs_queue.send_message.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    def test_player_param_with_organizer_role_dispatches(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        aws = _make_aws()
        event = _make_event(inputs={"player": "some_user"})
        result = deactivate_league_participant(event, aws)
        self.assertIsInstance(result, ResponseMessage)
        aws.sheets_agent_sqs_queue.send_message.assert_called_once()
        self.assertEqual(_get_dispatched_command(aws), "league-deactivate")


if __name__ == "__main__":
    unittest.main()
