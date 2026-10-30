import unittest
from unittest.mock import Mock, patch

import commands.score.score_commands as score_commands
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData

_KEY = {"PK": "SERVER#server123", "SK": "EVENT#event_111"}


def _make_event_data(scores=None, score_enabled=True):
    return EventData(
        checked_in={},
        registered={},
        queue={},
        participant_role=None,
        check_in_enabled=False,
        register_enabled=False,
        start_message="",
        end_message="",
        event_id="event_111",
        event_name="Wins Series",
        scores=scores if scores is not None else {},
        score_enabled=score_enabled,
    )


def _make_event(**kwargs):
    event = Mock()
    event.get_server_id.return_value = "server123"
    event.get_user_id.return_value = kwargs.get("user_id", "user_abc")
    event.get_username.return_value = kwargs.get("username", "TestUser")
    event.event_body = kwargs.get("event_body", {})
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


@patch("commands.score.score_commands.score_helper")
@patch("commands.score.score_commands.db_helper")
class TestScoreAdd(unittest.TestCase):
    def test_defaults_amount_to_one_for_calling_user(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())
        mock_helper.add_score.return_value = 1

        result = score_commands.score_add(_make_event(), _make_aws())

        args = mock_helper.add_score.call_args.args
        self.assertEqual(args[2:], ("user_abc", "TestUser", 1))
        self.assertIn("is now **1**", result.content)

    def test_uses_given_amount_with_no_upper_limit(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())
        mock_helper.add_score.return_value = 500

        score_commands.score_add(_make_event(inputs={"amount": 500}), _make_aws())

        self.assertEqual(mock_helper.add_score.call_args.args[4], 500)

    def test_rejects_amount_below_one_before_any_lookup(self, mock_db, mock_helper):
        result = score_commands.score_add(_make_event(inputs={"amount": 0}), _make_aws())

        self.assertIn("at least 1", result.content)
        mock_db.get_server_event_data_or_fail.assert_not_called()
        mock_helper.add_score.assert_not_called()

    def test_rejected_while_scoreboard_closed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(score_enabled=False))

        result = score_commands.score_add(_make_event(), _make_aws())

        self.assertIn("not being accepted", result.content)
        mock_helper.add_score.assert_not_called()

    def test_legacy_event_closed_when_flag_missing(self, mock_db, mock_helper):
        _patch_db(mock_db, EventData.from_dynamodb({"SK": "EVENT#event_111"}))

        result = score_commands.score_add(_make_event(), _make_aws())

        self.assertIn("not being accepted", result.content)

    def test_initializes_map_before_writing(self, mock_db, mock_helper):
        event_data = _make_event_data()
        _patch_db(mock_db, event_data)
        mock_helper.add_score.return_value = 1
        aws = _make_aws()

        score_commands.score_add(_make_event(), aws)

        mock_helper.ensure_scores_map.assert_called_once_with(aws.dynamodb_table, _KEY, event_data)

    def test_lost_race_asks_user_to_retry(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())
        mock_helper.add_score.return_value = None

        result = score_commands.score_add(_make_event(), _make_aws())

        self.assertEqual(result.content, score_commands.RETRY_MESSAGE)

    def test_event_lookup_failure_is_propagated(self, mock_db, mock_helper):
        mock_db.get_server_event_data_or_fail.return_value = ResponseMessage(content="event not found")

        result = score_commands.score_add(_make_event(), _make_aws())

        self.assertIn("event not found", result.content)


@patch("commands.score.score_commands.score_helper")
@patch("commands.score.score_commands.db_helper")
class TestScoreDeduct(unittest.TestCase):
    def test_deducts_from_calling_user(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(scores={"user_abc": {"display_name": "TestUser", "score": 5}}))
        mock_helper.deduct_score.return_value = 3

        result = score_commands.score_deduct(_make_event(inputs={"amount": 2}), _make_aws())

        self.assertEqual(mock_helper.deduct_score.call_args.args[2:], ("user_abc", "TestUser", 2))
        self.assertIn("is now **3**", result.content)

    def test_no_entry_rejected_without_write(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(scores={}))

        result = score_commands.score_deduct(_make_event(), _make_aws())

        self.assertIn("don't have a score", result.content)
        mock_helper.deduct_score.assert_not_called()

    def test_would_go_negative_reports_current_score(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(scores={"user_abc": {"display_name": "TestUser", "score": 3}}))
        mock_helper.deduct_score.return_value = None

        result = score_commands.score_deduct(_make_event(inputs={"amount": 5}), _make_aws())

        self.assertIn("score is **3**", result.content)

    def test_rejected_while_scoreboard_closed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(score_enabled=False))

        result = score_commands.score_deduct(_make_event(), _make_aws())

        self.assertIn("not being accepted", result.content)
        mock_helper.deduct_score.assert_not_called()


@patch("commands.score.score_commands.score_helper")
@patch("commands.score.score_commands.db_helper")
class TestScoreSet(unittest.TestCase):
    def test_sets_calling_users_score(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())

        result = score_commands.score_set(_make_event(inputs={"score": 7}), _make_aws())

        self.assertEqual(mock_helper.set_score.call_args.args[2:], ("user_abc", "TestUser", 7))
        self.assertIn("is now **7**", result.content)

    def test_zero_is_allowed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data())

        score_commands.score_set(_make_event(inputs={"score": 0}), _make_aws())

        mock_helper.set_score.assert_called_once()

    def test_negative_rejected(self, mock_db, mock_helper):
        result = score_commands.score_set(_make_event(inputs={"score": -1}), _make_aws())

        self.assertIn("can't be negative", result.content)
        mock_helper.set_score.assert_not_called()

    def test_rejected_while_scoreboard_closed(self, mock_db, mock_helper):
        _patch_db(mock_db, _make_event_data(score_enabled=False))

        result = score_commands.score_set(_make_event(inputs={"score": 7}), _make_aws())

        self.assertIn("not being accepted", result.content)
        mock_helper.set_score.assert_not_called()


@patch("commands.score.score_commands.db_helper")
class TestViews(unittest.TestCase):
    def test_score_view_shows_rank_even_while_closed(self, mock_db):
        scores = {
            "other": {"display_name": "Other", "score": 9},
            "user_abc": {"display_name": "TestUser", "score": 4},
        }
        _patch_db(mock_db, _make_event_data(scores=scores, score_enabled=False))

        result = score_commands.score_view(_make_event(), _make_aws())

        self.assertIn("**#2**", result.content)
        self.assertIn("**4**", result.content)

    def test_score_view_without_entry(self, mock_db):
        _patch_db(mock_db, _make_event_data(scores={}))

        result = score_commands.score_view(_make_event(), _make_aws())

        self.assertIn("don't have a score", result.content)

    def test_scoreboard_is_silent_and_sorted(self, mock_db):
        scores = {
            "low": {"display_name": "Low", "score": 1},
            "high": {"display_name": "High", "score": 6},
        }
        _patch_db(mock_db, _make_event_data(scores=scores, score_enabled=False))

        result = score_commands.show_scoreboard(_make_event(), _make_aws())

        self.assertLess(result.content.index("<@high>"), result.content.index("<@low>"))
        self.assertEqual(result.allowed_mentions, {"parse": []})

    def test_empty_scoreboard(self, mock_db):
        _patch_db(mock_db, _make_event_data(scores=None))

        result = score_commands.show_scoreboard(_make_event(), _make_aws())

        self.assertIn("no scores yet", result.content)


@patch("commands.score.score_commands.score_helper")
@patch("commands.score.score_commands.db_helper")
@patch("commands.score.score_commands.permissions_helper")
class TestOrganizerCommands(unittest.TestCase):
    def test_organizer_commands_require_organizer_role(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = ResponseMessage(content="no permission")
        aws = _make_aws()
        event = _make_event(inputs={"user": "target", "score": 1, "state": "Start"})

        for command in (
            score_commands.toggle_scoreboard,
            score_commands.reset_scoreboard,
            score_commands.score_override,
            score_commands.score_remove,
        ):
            self.assertIn("no permission", command(event, aws).content)

        mock_db.get_server_event_data_or_fail.assert_not_called()
        aws.dynamodb_table.update_item.assert_not_called()
        mock_helper.set_score.assert_not_called()
        mock_helper.reset_scores.assert_not_called()
        mock_helper.remove_score.assert_not_called()

    def test_toggle_start_opens_scoreboard(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(score_enabled=False))
        aws = _make_aws()

        result = score_commands.toggle_scoreboard(_make_event(inputs={"state": "Start"}), aws)

        call_kwargs = aws.dynamodb_table.update_item.call_args.kwargs
        self.assertEqual(call_kwargs["Key"], _KEY)
        self.assertIn(True, call_kwargs["ExpressionAttributeValues"].values())
        self.assertIn("Scoreboard open", result.content)

    def test_toggle_end_closes_scoreboard(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data())
        aws = _make_aws()

        result = score_commands.toggle_scoreboard(_make_event(inputs={"state": "End"}), aws)

        self.assertIn(False, aws.dynamodb_table.update_item.call_args.kwargs["ExpressionAttributeValues"].values())
        self.assertIn("Scoreboard closed", result.content)

    def test_reset_clears_scores(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(scores={"a": {"display_name": "A", "score": 1}}))
        aws = _make_aws()

        result = score_commands.reset_scoreboard(_make_event(), aws)

        mock_helper.reset_scores.assert_called_once_with(aws.dynamodb_table, _KEY)
        self.assertIn("has been reset", result.content)

    def test_reset_with_no_scores_skips_write(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(scores={}))

        result = score_commands.reset_scoreboard(_make_event(), _make_aws())

        self.assertIn("no scores to clear", result.content)
        mock_helper.reset_scores.assert_not_called()

    def test_override_sets_target_score_with_resolved_name_even_while_closed(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(score_enabled=False))
        event_body = {"data": {"resolved": {"users": {"target": {"global_name": "Target G", "username": "target_u"}}}}}
        event = _make_event(inputs={"user": "target", "score": 12}, event_body=event_body)

        result = score_commands.score_override(event, _make_aws())

        self.assertEqual(mock_helper.set_score.call_args.args[2:], ("target", "Target G", 12))
        self.assertIn("<@target>", result.content)
        self.assertEqual(result.allowed_mentions, {"parse": []})

    def test_override_rejects_negative_score(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None

        result = score_commands.score_override(_make_event(inputs={"user": "target", "score": -3}), _make_aws())

        self.assertIn("can't be negative", result.content)
        mock_helper.set_score.assert_not_called()

    def test_remove_drops_target(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(scores={"target": {"display_name": "T", "score": 2}}))
        aws = _make_aws()

        result = score_commands.score_remove(_make_event(inputs={"user": "target"}), aws)

        mock_helper.remove_score.assert_called_once_with(aws.dynamodb_table, _KEY, "target")
        self.assertIn("Removed", result.content)

    def test_remove_missing_target_skips_write(self, mock_perms, mock_db, mock_helper):
        mock_perms.verify_has_organizer_role.return_value = None
        _patch_db(mock_db, _make_event_data(scores={}))

        result = score_commands.score_remove(_make_event(inputs={"user": "target"}), _make_aws())

        self.assertIn("has no score", result.content)
        mock_helper.remove_score.assert_not_called()
