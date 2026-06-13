import unittest

import commands.startgg.startgg_commands as startgg_commands


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


if __name__ == "__main__":
    unittest.main()
