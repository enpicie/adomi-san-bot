# Env vars and the worker sys.path entry are set in tests/deferred_worker/__init__.py.
import unittest
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, patch

import requests

import discord_followup
import event_commands
import worker_startgg_api

import commands.event.startgg.startgg_api as src_startgg_api


_SLUG_URL = "https://www.start.gg/tournament/cte-2/event/cte-bracket"


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


_FUTURE = _iso(datetime.now(dt_timezone.utc) + timedelta(days=7))
_PAST = _iso(datetime.now(dt_timezone.utc) - timedelta(days=7))


def _event_body(**inputs):
    options = [{"name": k, "value": v} for k, v in inputs.items()]
    return {
        "guild_id": "server123",
        "application_id": "app1",
        "token": "interaction-token",
        "data": {"name": "event-create-startgg", "options": options},
        "member": {"user": {"id": "user1"}, "roles": ["organizer_role"]},
    }


_UNSET = object()


def _startgg_payload(event_name="Chained to Eternity 2", start=_UNSET, participants=None, no_discord=None):
    return {
        "event_name": event_name,
        "start_time_utc": _FUTURE if start is _UNSET else start,
        "location": "Online",
        "participants": participants if participants is not None else [],
        "no_discord_participants": no_discord if no_discord is not None else [],
    }


def _aws(table=None):
    services = Mock()
    services.dynamodb_table = table or Mock()
    return services


class _WorkerCreateFixture(unittest.TestCase):
    """Shared mocks for handle_event_create_startgg. Holds no tests itself."""

    def setUp(self):
        self.patches = {
            name: patch.object(event_commands, name)
            for name in ("db_helper", "startgg_api", "discord_api", "schedule_sync", "claims", "timezone_helper")
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}
        for p in self.patches.values():
            self.addCleanup(p.stop)

        self.mocks["db_helper"].get_server_config.return_value = {"should_always_remind": False}
        self.mocks["db_helper"].get_command_input.side_effect = self._input
        self.mocks["db_helper"].get_full_events_for_server.return_value = []
        self.mocks["db_helper"].event_key.side_effect = lambda s, e: {"PK": f"SERVER#{s}", "SK": f"EVENT#{e}"}
        self.mocks["db_helper"].SERVER_CONFIG_MISSING = "not set up"
        self.mocks["startgg_api"].query_startgg_event.return_value = _startgg_payload()
        self.mocks["startgg_api"].extract_startgg_slug.return_value = "tournament/cte-2/event/cte-bracket"
        self.mocks["timezone_helper"].to_utc_iso.return_value = _FUTURE
        self.mocks["claims"].try_claim_event_create.return_value = True
        self.mocks["discord_api"].create_scheduled_event.return_value = "1547629495949860884"
        self.inputs = {"event_link": _SLUG_URL, "end_time": "2026-09-27 02:00", "timezone": "UTC"}

    def _input(self, event_body, name):
        return self.inputs.get(name)


class TestHandleEventCreateStartgg(_WorkerCreateFixture):
    def test_creates_the_discord_event_and_persists_it(self):
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.mocks["discord_api"].create_scheduled_event.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["event_id"], "1547629495949860884")
        self.assertEqual(item["event_name"], "Chained to Eternity 2")
        self.assertEqual(item["startgg_url"], _SLUG_URL)
        self.assertIn("created with 0 registered participants", result)

    def test_participants_are_stored_keyed_by_discord_id(self):
        self.mocks["startgg_api"].query_startgg_event.return_value = _startgg_payload(
            participants=[{"display_name": "Kai", "user_id": "discord_1", "time_added": _FUTURE,
                           "source": "startgg", "external_id": "77"}],
            no_discord=[{"display_name": "NoLink", "user_id": "no_id", "time_added": _FUTURE}],
        )
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        registered = table.put_item.call_args.kwargs["Item"]["registered"]
        self.assertEqual(registered["discord_1"]["display_name"], "Kai")
        # Entrants without a linked Discord account are keyed by display name.
        self.assertEqual(registered["NoLink"]["user_id"], "no_id")
        self.assertIn("created with 2 registered participants", result)
        self.assertIn("do not have Discord linked", result)

    def test_duplicate_bracket_is_refused_without_creating(self):
        self.mocks["db_helper"].get_full_events_for_server.return_value = [{
            "event_id": "existing", "event_name": "Chained to Eternity 2",
            "startgg_url": _SLUG_URL, "end_time": _FUTURE,
        }]
        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["discord_api"].create_scheduled_event.assert_not_called()
        self.assertIn("already exists", result)

    def test_ended_event_does_not_block_a_new_one_on_the_same_bracket(self):
        self.mocks["db_helper"].get_full_events_for_server.return_value = [{
            "event_id": "old", "event_name": "Chained to Eternity 2",
            "startgg_url": _SLUG_URL, "end_time": _PAST,
        }]
        event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["discord_api"].create_scheduled_event.assert_called_once()

    def test_redelivered_message_loses_the_claim_and_creates_nothing(self):
        # SQS delivers at least once, so the same create can arrive twice.
        self.mocks["claims"].try_claim_event_create.return_value = False
        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["discord_api"].create_scheduled_event.assert_not_called()
        self.assertIn("already creating", result)

    def test_claim_is_taken_before_the_discord_event_exists(self):
        order = []
        self.mocks["claims"].try_claim_event_create.side_effect = lambda *a, **k: order.append("claim") or True
        self.mocks["discord_api"].create_scheduled_event.side_effect = lambda *a, **k: order.append("create") or "id1"

        event_commands.handle_event_create_startgg(_event_body(), _aws())

        # Creating first would orphan a Discord event the loser could not clean up.
        self.assertEqual(order, ["claim", "create"])

    def test_claim_is_keyed_on_the_bracket_slug(self):
        event_commands.handle_event_create_startgg(_event_body(), _aws())

        args = self.mocks["claims"].try_claim_event_create.call_args.args
        self.assertEqual(args[0], "server123")
        self.assertEqual(args[1], "startgg:tournament/cte-2/event/cte-bracket")

    def test_past_start_time_is_pushed_forward_and_reported(self):
        self.mocks["startgg_api"].query_startgg_event.return_value = _startgg_payload(start=_PAST)
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.assertIn("is in the past", result)
        self.assertGreater(table.put_item.call_args.kwargs["Item"]["start_time"], _PAST)

    def test_missing_start_time_reports_instead_of_creating(self):
        self.mocks["startgg_api"].query_startgg_event.return_value = _startgg_payload(start=None)
        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["discord_api"].create_scheduled_event.assert_not_called()
        self.assertIn("`/event-create`", result)

    def test_schedule_message_is_rebuilt_after_creating(self):
        event_commands.handle_event_create_startgg(_event_body(), _aws())
        self.mocks["schedule_sync"].sync_schedule.assert_called_once()

    def test_unconfigured_server_is_reported_without_querying_startgg(self):
        self.mocks["db_helper"].get_server_config.return_value = None
        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["startgg_api"].query_startgg_event.assert_not_called()
        self.assertEqual(result, "not set up")

    def test_missing_participant_role_warns(self):
        result = event_commands.handle_event_create_startgg(_event_body(), _aws())
        self.assertIn("No participant role is set", result)


    def test_custom_event_name_overrides_the_startgg_name(self):
        # Intentional, requested feature: the optional event_name input wins.
        self.inputs["event_name"] = "Custom Override Name"
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.assertEqual(self.mocks["discord_api"].create_scheduled_event.call_args.kwargs["name"], "Custom Override Name")
        self.assertEqual(table.put_item.call_args.kwargs["Item"]["event_name"], "Custom Override Name")
        self.assertIn("Custom Override Name", result)
        self.assertNotIn("Chained to Eternity 2", result)

    def test_absent_event_name_falls_back_to_the_startgg_name(self):
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.assertEqual(self.mocks["discord_api"].create_scheduled_event.call_args.kwargs["name"], "Chained to Eternity 2")
        self.assertEqual(table.put_item.call_args.kwargs["Item"]["event_name"], "Chained to Eternity 2")
        self.assertIn("Chained to Eternity 2", result)


class TestHandleEventCreateStartggClaimRelease(_WorkerCreateFixture):
    """The claim guards only the in-flight window of one create. Left in place it
    blocks a delete-then-recreate of the same bracket, or a corrected retry, until
    DynamoDB sweeps it days later."""

    _IDENTITY = "startgg:tournament/cte-2/event/cte-bracket"

    def test_claim_is_released_after_a_successful_create(self):
        table = Mock()
        event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        table.put_item.assert_called_once()
        self.mocks["claims"].release_event_create_claim.assert_called_once_with("server123", self._IDENTITY, table)

    def test_discord_rejection_is_shown_to_the_organizer_and_the_claim_released(self):
        # MIRROR of bot.py: a ValueError's text is the user's message. Before the
        # move to the worker this was the behaviour; the worker's generic error
        # would hide why the create failed.
        self.mocks["discord_api"].create_scheduled_event.side_effect = ValueError(
            "Scheduled end time must be after scheduled start time"
        )
        table = Mock()
        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.assertEqual(result, "Scheduled end time must be after scheduled start time")
        table.put_item.assert_not_called()
        self.mocks["schedule_sync"].sync_schedule.assert_not_called()
        self.mocks["claims"].release_event_create_claim.assert_called_once_with("server123", self._IDENTITY, table)

    def test_unexpected_failure_releases_the_claim_and_still_propagates(self):
        # The handler turns this into the generic error; the claim must not outlive it.
        table = Mock()
        table.put_item.side_effect = RuntimeError("dynamodb down")

        with self.assertRaisesRegex(RuntimeError, "dynamodb down"):
            event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.mocks["claims"].release_event_create_claim.assert_called_once_with("server123", self._IDENTITY, table)

    def test_duplicate_that_appears_after_the_claim_is_refused_without_creating(self):
        # Another delivery's put can land between our first check and our claim,
        # and its release can come before our claim: the claim is won, but the
        # event already exists. The second check stops the second event.
        existing = {"event_id": "other", "event_name": "Chained to Eternity 2",
                    "startgg_url": _SLUG_URL, "end_time": _FUTURE}
        self.mocks["db_helper"].get_full_events_for_server.side_effect = [[], [existing]]
        table = Mock()

        result = event_commands.handle_event_create_startgg(_event_body(), _aws(table))

        self.mocks["discord_api"].create_scheduled_event.assert_not_called()
        table.put_item.assert_not_called()
        self.assertIn("already exists", result)
        self.mocks["claims"].release_event_create_claim.assert_called_once_with("server123", self._IDENTITY, table)

    def test_a_lost_claim_is_never_released(self):
        # Releasing here would delete the claim of the delivery that is creating.
        self.mocks["claims"].try_claim_event_create.return_value = False
        event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.mocks["claims"].release_event_create_claim.assert_not_called()


class TestHandleEventCreateStartggUserFacingFailures(_WorkerCreateFixture):
    def test_start_gg_outage_tells_the_organizer_to_try_again(self):
        self.mocks["startgg_api"].StartggUnavailableError = worker_startgg_api.StartggUnavailableError
        self.mocks["startgg_api"].query_startgg_event.side_effect = worker_startgg_api.StartggUnavailableError(
            worker_startgg_api.STARTGG_UNAVAILABLE_MESSAGE
        )

        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.assertEqual(result, worker_startgg_api.STARTGG_UNAVAILABLE_MESSAGE)
        self.mocks["discord_api"].create_scheduled_event.assert_not_called()

    def test_reply_with_many_unlinked_players_fits_in_one_discord_message(self):
        no_discord = [
            {"display_name": f"UnlinkedPlayer{i}", "user_id": "no_id", "time_added": _FUTURE} for i in range(400)
        ]
        self.mocks["startgg_api"].query_startgg_event.return_value = _startgg_payload(no_discord=no_discord)

        result = event_commands.handle_event_create_startgg(_event_body(), _aws())

        self.assertLessEqual(len(result), 2000)
        self.assertIn("more", result)


class TestWorkerStartggQueryOutage(unittest.TestCase):
    def test_request_failure_becomes_a_user_facing_error(self):
        with (
            patch.object(worker_startgg_api, "_get_startgg_api_token", return_value="fake-token"),
            patch.object(worker_startgg_api, "_post_graphql", side_effect=requests.ConnectionError("down")),
        ):
            with self.assertRaises(worker_startgg_api.StartggUnavailableError) as ctx:
                worker_startgg_api.query_startgg_event(_SLUG_URL)
        self.assertEqual(str(ctx.exception), worker_startgg_api.STARTGG_UNAVAILABLE_MESSAGE)

    def test_message_matches_the_src_twin(self):
        self.assertEqual(worker_startgg_api.STARTGG_UNAVAILABLE_MESSAGE, src_startgg_api.STARTGG_UNAVAILABLE_MESSAGE)


class TestFollowupFitsDiscordLimit(unittest.TestCase):
    def test_oversized_followup_is_trimmed_rather_than_rejected(self):
        with patch.object(discord_followup.requests, "post") as post:
            post.return_value.ok = True
            discord_followup.send_followup("app1", "token", "x" * 5000)

        sent = post.call_args.kwargs["json"]["content"]
        self.assertLessEqual(len(sent), discord_followup.DISCORD_MESSAGE_LIMIT)
        self.assertIn("trimmed", sent)

    def test_normal_followup_is_sent_unchanged(self):
        with patch.object(discord_followup.requests, "post") as post:
            post.return_value.ok = True
            discord_followup.send_followup("app1", "token", "✅ done")

        self.assertEqual(post.call_args.kwargs["json"]["content"], "✅ done")


if __name__ == "__main__":
    unittest.main()
