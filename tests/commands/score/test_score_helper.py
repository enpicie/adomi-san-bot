import os
import unittest
from unittest.mock import Mock

# Fake AWS credentials/region so moto never touches a real account.
os.environ["AWS_ACCESS_KEY_ID"] = "test-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-key"
os.environ["AWS_SECURITY_TOKEN"] = "test-token"
os.environ["AWS_SESSION_TOKEN"] = "test-token"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws

import commands.score.score_constants as score_constants
import commands.score.score_helper as score_helper
from database.models.event_data import EventData

_KEY = {"PK": "SERVER#server123", "SK": "EVENT#event_111"}


def _event_data(scores):
    return EventData(
        checked_in={}, registered={}, queue={}, participant_role=None,
        check_in_enabled=False, register_enabled=False, start_message="", end_message="",
        event_id="event_111", scores=scores,
    )


def _entry(name, score):
    return {"display_name": name, "score": score}


class ScoreTableTestCase(unittest.TestCase):
    """Runs the real update expressions against a moto-backed table."""

    def setUp(self):
        self._mock_aws = mock_aws()
        self._mock_aws.start()
        self.addCleanup(self._mock_aws.stop)
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.table = dynamodb.create_table(
            TableName="test-table",
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
        )

    def _put_event(self, **attrs):
        self.table.put_item(Item={**_KEY, **attrs})

    def _scores(self):
        return self.table.get_item(Key=_KEY)["Item"].get("scores")


class TestEnsureScoresMap(ScoreTableTestCase):
    def test_creates_map_on_legacy_event_so_nested_writes_succeed(self):
        self._put_event()  # predates scoreboards: no `scores` attribute
        score_helper.ensure_scores_map(self.table, _KEY, _event_data(scores=None))
        score_helper.set_score(self.table, _KEY, "u1", "Alice", 3)
        self.assertEqual(self._scores(), {"u1": _entry("Alice", 3)})

    def test_skips_write_when_map_already_loaded(self):
        table = Mock()
        score_helper.ensure_scores_map(table, _KEY, _event_data(scores={}))
        table.update_item.assert_not_called()

    def test_does_not_clobber_existing_scores(self):
        self._put_event(scores={"u1": _entry("Alice", 4)})
        # Stale read said the map was missing; if_not_exists must keep the real one.
        score_helper.ensure_scores_map(self.table, _KEY, _event_data(scores=None))
        self.assertEqual(self._scores(), {"u1": _entry("Alice", 4)})


class TestChangeScore(ScoreTableTestCase):
    def test_first_add_creates_entry_with_amount(self):
        self._put_event(scores={})
        new_score = score_helper.change_score(self.table, _KEY, "u1", "Alice", 2)
        self.assertEqual(new_score, 2)
        self.assertEqual(self._scores(), {"u1": _entry("Alice", 2)})

    def test_add_increments_existing_entry_and_refreshes_name(self):
        self._put_event(scores={"u1": _entry("OldName", 5)})
        new_score = score_helper.change_score(self.table, _KEY, "u1", "Alice", 3)
        self.assertEqual(new_score, 8)
        self.assertEqual(self._scores(), {"u1": _entry("Alice", 8)})

    def test_add_leaves_other_players_untouched(self):
        self._put_event(scores={"u2": _entry("Bob", 7)})
        score_helper.change_score(self.table, _KEY, "u1", "Alice", 1)
        self.assertEqual(self._scores()["u2"], _entry("Bob", 7))

    def test_returns_none_when_race_is_lost_twice(self):
        condition_failed = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        table = Mock()
        table.update_item.side_effect = condition_failed
        self.assertIsNone(score_helper.change_score(table, _KEY, "u1", "Alice", 1))
        self.assertEqual(table.update_item.call_count, 3)

    def test_non_condition_errors_propagate(self):
        table = Mock()
        table.update_item.side_effect = ClientError({"Error": {"Code": "ValidationException"}}, "UpdateItem")
        with self.assertRaises(ClientError):
            score_helper.change_score(table, _KEY, "u1", "Alice", 1)


    def test_negative_delta_can_go_below_zero(self):
        self._put_event(scores={"u1": _entry("Alice", 3)})
        self.assertEqual(score_helper.change_score(self.table, _KEY, "u1", "Alice", -5), -2)
        self.assertEqual(self._scores()["u1"]["score"], -2)

    def test_negative_delta_without_entry_creates_negative_entry(self):
        self._put_event(scores={})
        self.assertEqual(score_helper.change_score(self.table, _KEY, "u1", "Alice", -1), -1)
        self.assertEqual(self._scores(), {"u1": _entry("Alice", -1)})


class TestSetRemoveReset(ScoreTableTestCase):
    def test_set_overwrites_existing_score(self):
        self._put_event(scores={"u1": _entry("Alice", 9)})
        score_helper.set_score(self.table, _KEY, "u1", "Alice", 4)
        self.assertEqual(self._scores()["u1"], _entry("Alice", 4))

    def test_remove_drops_only_that_entry(self):
        self._put_event(scores={"u1": _entry("Alice", 1), "u2": _entry("Bob", 2)})
        score_helper.remove_score(self.table, _KEY, "u1")
        self.assertEqual(self._scores(), {"u2": _entry("Bob", 2)})

    def test_reset_clears_all_entries(self):
        self._put_event(scores={"u1": _entry("Alice", 1), "u2": _entry("Bob", 2)})
        score_helper.reset_scores(self.table, _KEY)
        self.assertEqual(self._scores(), {})


class TestRanking(unittest.TestCase):
    def test_ties_share_rank_and_next_rank_skips(self):
        scores = {
            "a": _entry("Alice", 5),
            "b": _entry("Bob", 5),
            "c": _entry("Cara", 3),
            "d": _entry("Dan", 0),
            "e": _entry("Eve", -2),
        }
        ranks = [(rank, user_id) for rank, user_id, _ in score_helper.rank_scores(scores)]
        self.assertEqual(ranks, [(1, "a"), (1, "b"), (3, "c"), (4, "d"), (5, "e")])

    def test_get_rank_returns_rank_and_entry(self):
        scores = {"a": _entry("Alice", 5), "b": _entry("Bob", 2)}
        rank, entry = score_helper.get_rank(scores, "b")
        self.assertEqual((rank, entry.score), (2, 2))

    def test_get_rank_returns_none_for_missing_user(self):
        self.assertIsNone(score_helper.get_rank({"a": _entry("Alice", 5)}, "z"))


class TestBuildScoreboard(unittest.TestCase):
    def test_lists_players_highest_first_with_pings(self):
        content = score_helper.build_scoreboard("HEADER", {"a": _entry("Alice", 1), "b": _entry("Bob", 4)})
        lines = content.split("\n")
        self.assertEqual(lines[0], "HEADER")
        self.assertIn("<@b>", lines[1])
        self.assertIn("**4**", lines[1])
        self.assertIn("<@a>", lines[2])

    def test_truncates_after_row_cap_with_remaining_count(self):
        cap = score_constants.SCOREBOARD_MAX_ROWS
        scores = {f"u{i}": _entry(f"P{i}", 1000 - i) for i in range(cap + 5)}
        content = score_helper.build_scoreboard("HEADER", scores)
        self.assertEqual(len(content.split("\n")), 1 + cap + 1)
        self.assertTrue(content.endswith("…and 5 more"))

    def test_does_not_split_a_tie_group_at_the_row_cap(self):
        cap = score_constants.SCOREBOARD_MAX_ROWS
        scores = {f"u{i}": _entry(f"P{i:03}", 1000 - i) for i in range(cap - 1)}
        # Three players tied for the last slot straddle the cap.
        for i in range(3):
            scores[f"t{i}"] = _entry(f"T{i}", 1)
        scores["low"] = _entry("Low", 0)
        content = score_helper.build_scoreboard("HEADER", scores)
        for i in range(3):
            self.assertIn(f"<@t{i}>", content)
        self.assertNotIn("<@low>", content)
        self.assertTrue(content.endswith("…and 1 more"))

    def test_never_exceeds_discord_message_limit(self):
        # One giant tie group would ignore the row cap; the character budget must still hold.
        scores = {f"{i:019d}": _entry(f"P{i}", 1) for i in range(200)}
        content = score_helper.build_scoreboard("HEADER", scores)
        self.assertLessEqual(len(content), 2000)
        self.assertIn("more", content.split("\n")[-1])
