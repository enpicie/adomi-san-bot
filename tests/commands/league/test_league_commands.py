import unittest
from unittest.mock import Mock, patch

from commands.league.league_commands import (
    create_league, update_league, sync_active_participants,
    join_league, toggle_join_league, LEAGUE_ID_MAX_LENGTH,
)
from commands.models.response_message import ResponseMessage
from database.models.league_data import LeagueData


def _make_league(
    league_id="TST",
    league_name="Test League",
    google_sheets_link="https://docs.google.com/spreadsheets/d/abc/edit",
    active_players=None,
    join_enabled=False,
    active_participant_role=None,
):
    return LeagueData(
        league_id=league_id,
        league_name=league_name,
        google_sheets_link=google_sheets_link,
        active_players=active_players or {},
        join_enabled=join_enabled,
        active_participant_role=active_participant_role,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = kwargs.get("server_id", "server123")
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    event.get_display_name.return_value = kwargs.get("display_name", "Alice")
    inputs = kwargs.get("inputs", {})
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_aws():
    aws = Mock()
    aws.dynamodb_table = Mock()
    aws.remove_role_sqs_queue = Mock()
    return aws


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
    def test_active_participant_role_stored_when_provided(self, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = ResponseMessage(content="not found")
        mock_db.build_server_pk.return_value = "SERVER#server123"
        aws = _make_aws()
        event = _make_event(inputs={
            "league_id": "TST",
            "league_name": "Test League",
            "google_sheets_link": "https://docs.google.com/spreadsheets/d/abc/edit",
            "active_participant_role": "role_999",
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
        event = _make_event(inputs={"league_id": "TST", "league_name": None, "google_sheets_link": None, "active_participant_role": None})
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
        event = _make_event(inputs={"league_id": "TST", "league_name": "New Name", "google_sheets_link": None, "active_participant_role": None})
        result = update_league(event, aws)
        aws.dynamodb_table.update_item.assert_called_once()
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("TST", result.content)

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = update_league(_make_event(), _make_aws())
        self.assertIn("no permission", result.content)


class TestSyncActiveParticipants(unittest.TestCase):
    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    @patch("commands.league.league_commands.discord_helper")
    @patch("commands.league.league_commands.role_removal_queue")
    def test_new_players_get_role_assigned(self, mock_queue, mock_discord, mock_sheets, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(
            active_players={"old_user": "Bob"},
            active_participant_role="role_123",
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        mock_sheets.get_active_participants.return_value = {"old_user": "Bob", "new_user": "Alice"}
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})

        sync_active_participants(event, aws)

        mock_discord.add_role_to_user.assert_called_once_with(
            guild_id="server123", user_id="new_user", role_id="role_123"
        )
        mock_queue.enqueue_remove_role_jobs.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    @patch("commands.league.league_commands.discord_helper")
    @patch("commands.league.league_commands.role_removal_queue")
    def test_removed_players_queued_for_role_removal(self, mock_queue, mock_discord, mock_sheets, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(
            active_players={"old_user": "Bob"},
            active_participant_role="role_123",
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        mock_sheets.get_active_participants.return_value = {}
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})

        sync_active_participants(event, aws)

        mock_queue.enqueue_remove_role_jobs.assert_called_once_with(
            server_id="server123",
            user_ids=["old_user"],
            role_id="role_123",
            sqs_queue=aws.remove_role_sqs_queue,
        )
        mock_discord.add_role_to_user.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    @patch("commands.league.league_commands.discord_helper")
    @patch("commands.league.league_commands.role_removal_queue")
    def test_no_role_configured_skips_discord_operations(self, mock_queue, mock_discord, mock_sheets, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(
            active_players={"old_user": "Bob"},
            active_participant_role=None,
        )
        mock_db.build_server_pk.return_value = "SERVER#server123"
        mock_sheets.get_active_participants.return_value = {"new_user": "Alice"}
        event = _make_event(inputs={"league_name": "TST"})

        sync_active_participants(event, _make_aws())

        mock_discord.add_role_to_user.assert_not_called()
        mock_queue.enqueue_remove_role_jobs.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    @patch("commands.league.league_commands.discord_helper")
    @patch("commands.league.league_commands.role_removal_queue")
    def test_active_players_written_to_db(self, mock_queue, mock_discord, mock_sheets, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league(active_players={})
        mock_db.build_server_pk.return_value = "SERVER#server123"
        mock_sheets.get_active_participants.return_value = {"u1": "Alice"}
        aws = _make_aws()
        event = _make_event(inputs={"league_name": "TST"})

        sync_active_participants(event, aws)

        aws.dynamodb_table.update_item.assert_called_once()
        update_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(update_kwargs["ExpressionAttributeValues"][":active_players"], {"u1": "Alice"})

    @patch("commands.league.league_commands.permissions_helper")
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    @patch("commands.league.league_commands.discord_helper")
    @patch("commands.league.league_commands.role_removal_queue")
    def test_sheet_permission_error_returns_error_message(self, mock_queue, mock_discord, mock_sheets, mock_db, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = None
        mock_db.get_server_league_data_or_fail.return_value = _make_league()
        mock_sheets.get_active_participants.side_effect = PermissionError("no access")
        event = _make_event(inputs={"league_name": "TST"})

        result = sync_active_participants(event, _make_aws())

        self.assertIsInstance(result, ResponseMessage)
        mock_queue.enqueue_remove_role_jobs.assert_not_called()

    @patch("commands.league.league_commands.permissions_helper")
    def test_missing_organizer_role_returns_error(self, mock_perms):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        result = sync_active_participants(_make_event(), _make_aws())
        self.assertIn("no permission", result.content)


class TestJoinLeague(unittest.TestCase):
    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    def test_join_disabled_returns_error(self, mock_sheets, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = _make_league(join_enabled=False)
        event = _make_event(inputs={"league_name": "TST"})
        result = join_league(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("not currently enabled", result.content)
        mock_sheets.append_league_participant.assert_not_called()

    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    def test_join_enabled_appends_participant(self, mock_sheets, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = _make_league(join_enabled=True)
        event = _make_event(user_id="u1", display_name="Alice", inputs={"league_name": "TST"})
        result = join_league(event, _make_aws())
        mock_sheets.append_league_participant.assert_called_once()
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Alice", result.content)

    @patch("commands.league.league_commands.db_helper")
    @patch("commands.league.league_commands.sheets_helper")
    def test_sheet_permission_error_returns_error_message(self, mock_sheets, mock_db):
        mock_db.get_server_league_data_or_fail.return_value = _make_league(join_enabled=True)
        mock_sheets.append_league_participant.side_effect = PermissionError("no access")
        event = _make_event(inputs={"league_name": "TST"})
        result = join_league(event, _make_aws())
        self.assertIsInstance(result, ResponseMessage)


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


if __name__ == "__main__":
    unittest.main()
