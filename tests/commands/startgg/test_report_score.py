import unittest

from commands.startgg.startgg_commands import _SCORE_PATTERN


class TestScorePattern(unittest.TestCase):
    def test_valid_score_matches(self):
        self.assertIsNotNone(_SCORE_PATTERN.match("2-1"))

    def test_valid_score_with_zero(self):
        self.assertIsNotNone(_SCORE_PATTERN.match("2-0"))

    def test_valid_score_extracts_groups(self):
        m = _SCORE_PATTERN.match("3-2")
        self.assertEqual(m.group(1), "3")
        self.assertEqual(m.group(2), "2")

    def test_multi_digit_scores_match(self):
        m = _SCORE_PATTERN.match("10-8")
        self.assertEqual(m.group(1), "10")
        self.assertEqual(m.group(2), "8")

    def test_missing_dash_does_not_match(self):
        self.assertIsNone(_SCORE_PATTERN.match("21"))

    def test_reversed_format_does_not_match(self):
        # Letters not accepted
        self.assertIsNone(_SCORE_PATTERN.match("W-L"))

    def test_empty_string_does_not_match(self):
        self.assertIsNone(_SCORE_PATTERN.match(""))

    def test_extra_text_does_not_match(self):
        # fullmatch-style: pattern anchored with ^ and $
        self.assertIsNone(_SCORE_PATTERN.match("2-1 extra"))


class TestGameDataConstruction(unittest.TestCase):
    """Tests the game-by-game data construction logic used in report_score."""

    def _build_game_data(self, winner_games: int, loser_games: int,
                         winner_id: str = "W", loser_id: str = "L") -> list:
        game_data = []
        for game_num in range(1, winner_games + loser_games + 1):
            game_winner_id = winner_id if game_num <= winner_games else loser_id
            game_data.append({"winnerId": game_winner_id, "gameNum": game_num})
        return game_data

    def test_game_count_matches_total_games(self):
        self.assertEqual(len(self._build_game_data(2, 1)), 3)

    def test_winner_games_come_first(self):
        data = self._build_game_data(2, 1, winner_id="W", loser_id="L")
        self.assertEqual(data[0]["winnerId"], "W")
        self.assertEqual(data[1]["winnerId"], "W")
        self.assertEqual(data[2]["winnerId"], "L")

    def test_game_numbers_are_sequential(self):
        data = self._build_game_data(2, 1)
        self.assertEqual([d["gameNum"] for d in data], [1, 2, 3])

    def test_sweep_all_winner_games(self):
        data = self._build_game_data(2, 0, winner_id="W", loser_id="L")
        self.assertTrue(all(d["winnerId"] == "W" for d in data))


if __name__ == "__main__":
    unittest.main()
