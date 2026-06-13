import unittest
from unittest.mock import Mock, patch

import commands.startgg.startgg_commands as startgg_commands
from commands.models.response_message import ResponseMessage


class TestParseScore(unittest.TestCase):
    """Tests _parse_score, which turns '<winner>-<loser>' strings into (int, int) or None."""

    def test_valid_score_returns_int_tuple(self):
        self.assertEqual(startgg_commands._parse_score("2-1"), (2, 1))

    def test_valid_sweep_score(self):
        self.assertEqual(startgg_commands._parse_score("3-0"), (3, 0))

    def test_zero_winner_games_still_parses(self):
        # _parse_score does not validate winner > loser; that happens elsewhere.
        self.assertEqual(startgg_commands._parse_score("0-3"), (0, 3))

    def test_multi_digit_scores_parse(self):
        self.assertEqual(startgg_commands._parse_score("10-8"), (10, 8))

    def test_whitespace_padded_score_is_stripped_and_parses(self):
        self.assertEqual(startgg_commands._parse_score("  2-1  "), (2, 1))

    def test_internal_spaces_around_dash_return_none(self):
        self.assertIsNone(startgg_commands._parse_score("2 - 1"))

    def test_letters_return_none(self):
        self.assertIsNone(startgg_commands._parse_score("a-b"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score(""))

    def test_three_part_score_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score("2-1-3"))

    def test_leading_negative_sign_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score("-1-2"))

    def test_missing_dash_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score("21"))

    def test_dq_string_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score("dq"))
        self.assertIsNone(startgg_commands._parse_score("DQ"))

    def test_extra_text_after_score_returns_none(self):
        self.assertIsNone(startgg_commands._parse_score("2-1 extra"))


class TestBuildSetGameData(unittest.TestCase):
    """Tests the real build_set_game_data used by report_score to build start.gg gameData."""

    def test_game_count_matches_total_games(self):
        data = startgg_commands.build_set_game_data(2, 1, "entrant-w", "entrant-l")
        self.assertEqual(len(data), 3)

    def test_winner_games_come_first_then_loser_games(self):
        data = startgg_commands.build_set_game_data(2, 1, "entrant-w", "entrant-l")
        self.assertEqual([g["winnerId"] for g in data], ["entrant-w", "entrant-w", "entrant-l"])

    def test_game_numbers_are_sequential_starting_at_one(self):
        data = startgg_commands.build_set_game_data(2, 1, "entrant-w", "entrant-l")
        self.assertEqual([g["gameNum"] for g in data], [1, 2, 3])

    def test_sweep_has_only_winner_games(self):
        data = startgg_commands.build_set_game_data(2, 0, "entrant-w", "entrant-l")
        self.assertEqual(len(data), 2)
        self.assertTrue(all(g["winnerId"] == "entrant-w" for g in data))

    def test_each_game_entry_has_exactly_winner_and_game_num_keys(self):
        data = startgg_commands.build_set_game_data(1, 1, "entrant-w", "entrant-l")
        for game in data:
            self.assertEqual(set(game.keys()), {"winnerId", "gameNum"})

    def test_zero_zero_returns_empty_list(self):
        self.assertEqual(startgg_commands.build_set_game_data(0, 0, "entrant-w", "entrant-l"), [])


def _make_event(**inputs):
    event = Mock()
    event.get_server_id.return_value = "server123"
    event.get_command_input_value.side_effect = lambda key: inputs.get(key)
    return event


def _make_config(startgg_oauth_token="oauth-token"):
    config = Mock()
    config.startgg_oauth_token = startgg_oauth_token
    return config


def _make_event_data(startgg_url="https://start.gg/tournament/t/event/e", registered=None):
    data = Mock()
    data.startgg_url = startgg_url
    data.registered = registered if registered is not None else {}
    return data


_REGISTERED = {
    "winner_user": {"display_name": "Winner", "user_id": "winner_user", "external_id": "entrant-w"},
    "loser_user": {"display_name": "Loser", "user_id": "loser_user", "external_id": "entrant-l"},
}


class TestReportScoreCommand(unittest.TestCase):
    """Behavior of the report_score command (the start.gg score-report flow), not just helpers."""

    @patch("commands.startgg.startgg_commands.startgg_api")
    @patch("commands.startgg.startgg_commands.db_helper")
    def test_happy_path_reports_set_and_confirms(self, mock_db, mock_api):
        mock_db.get_server_config_or_fail.return_value = _make_config()
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(registered=_REGISTERED)
        mock_api.extract_startgg_slug.return_value = "tournament/t/event/e"
        # find_set_between_players -> (set_id, entrant_ids_map, is_completed=False)
        mock_api.find_set_between_players.return_value = (
            "set_1", {"entrant-w": "set-entrant-w", "entrant-l": "set-entrant-l"}, False
        )
        aws = Mock()
        aws.dynamodb_table = Mock()
        event = _make_event(
            event_name="evt1", winner="winner_user", loser="loser_user", score="2-1"
        )

        result = startgg_commands.report_score(event, aws)

        # Outcome: the set is reported to start.gg and the user gets a confirmation.
        mock_api.report_set.assert_called_once()
        self.assertIsInstance(result, ResponseMessage)
        self.assertIn("Score reported on start.gg", result.content)

    @patch("commands.startgg.startgg_commands.startgg_api")
    @patch("commands.startgg.startgg_commands.db_helper")
    def test_no_oauth_token_returns_auth_required_without_reporting(self, mock_db, mock_api):
        mock_db.get_server_config_or_fail.return_value = _make_config(startgg_oauth_token=None)
        aws = Mock()
        event = _make_event(
            event_name="evt1", winner="winner_user", loser="loser_user", score="2-1"
        )

        result = startgg_commands.report_score(event, aws)

        self.assertIn("must be linked", result.content)
        mock_api.report_set.assert_not_called()

    @patch("commands.startgg.startgg_commands.startgg_api")
    @patch("commands.startgg.startgg_commands.db_helper")
    def test_no_open_set_found_returns_error_without_reporting(self, mock_db, mock_api):
        mock_db.get_server_config_or_fail.return_value = _make_config()
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(registered=_REGISTERED)
        mock_api.extract_startgg_slug.return_value = "tournament/t/event/e"
        mock_api.find_set_between_players.return_value = None
        aws = Mock()
        event = _make_event(
            event_name="evt1", winner="winner_user", loser="loser_user", score="2-1"
        )

        result = startgg_commands.report_score(event, aws)

        self.assertIn("Could not find an open set", result.content)
        mock_api.report_set.assert_not_called()

    @patch("commands.startgg.startgg_commands.db_helper")
    def test_invalid_score_format_returns_error_before_lookups(self, mock_db):
        aws = Mock()
        event = _make_event(
            event_name="evt1", winner="winner_user", loser="loser_user", score="not-a-score"
        )

        result = startgg_commands.report_score(event, aws)

        self.assertIn("Invalid score format", result.content)
        mock_db.get_server_config_or_fail.assert_not_called()


if __name__ == "__main__":
    unittest.main()
