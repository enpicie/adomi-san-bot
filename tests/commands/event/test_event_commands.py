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


def _make_linked_event_data(start, end, startgg_url="https://www.start.gg/tournament/t/event/e",
                            event_id="event_111", event_name="Weekly Bracket"):
    return EventData(
        checked_in={},
        registered={},
        queue={},
        participant_role=None,
        check_in_enabled=False,
        register_enabled=True,
        start_message="",
        end_message="",
        start_time=start,
        end_time=end,
        event_id=event_id,
        event_name=event_name,
        startgg_url=startgg_url,
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
    aws.deferred_worker_sqs_queue = Mock()
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


class TestCreateEventStartggDefers(unittest.TestCase):
    """The start.gg query alone can exceed Discord's 3s deadline, so this command
    validates, rejects an obvious repeat, and hands the work to the worker."""

    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_valid_link_is_dispatched_and_acknowledged(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_event_helper.find_duplicate_event.return_value = None
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/tournament/t/event/e",
                                    "end_time": "2026-09-27 02:00", "timezone": "UTC"})

        result = event_commands.create_event_startgg(event, aws)

        mock_dispatch.dispatch.assert_called_once_with("event-create-startgg", event, aws)
        # Nothing is created inline any more — that is the worker's job.
        mock_event_helper.create_event_record.assert_not_called()
        aws.dynamodb_table.update_item.assert_not_called()
        self.assertIn("start.gg", result.content)

    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_unparseable_end_time_is_rejected_before_queueing(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch, mock_tz
    ):
        # Once queued, a bad end time could only be reported as a followup later.
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_tz.to_utc_iso.side_effect = ValueError("bad format")
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/tournament/t/event/e",
                                    "end_time": "tomorrow-ish", "timezone": "UTC"})

        result = event_commands.create_event_startgg(event, aws)

        mock_dispatch.dispatch.assert_not_called()
        self.assertEqual(result.content, event_commands.INVALID_END_TIME_MESSAGE)

    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_invalid_link_is_rejected_without_dispatching(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = False
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://example.com/nope"})

        result = event_commands.create_event_startgg(event, aws)

        mock_dispatch.dispatch.assert_not_called()
        self.assertEqual(result.content, event_commands.INVALID_STARTGG_LINK_MESSAGE)

    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_known_duplicate_link_is_rejected_before_queueing(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_event_helper.find_duplicate_event.return_value = _make_event_data(
            event_name="Chained to Eternity 2"
        )
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/tournament/t/event/e",
                                    "end_time": "2026-09-27 02:00", "timezone": "UTC"})

        result = event_commands.create_event_startgg(event, aws)

        mock_dispatch.dispatch.assert_not_called()
        self.assertIn("Chained to Eternity 2", result.content)

    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_duplicate_lookup_is_keyed_on_the_link_not_the_name(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch
    ):
        # The event name is only known after the start.gg query, which has not
        # happened yet at this point — the link is all we can match on.
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_api.is_valid_startgg_url.return_value = True
        mock_event_helper.find_duplicate_event.return_value = None
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/tournament/t/event/e",
                                    "end_time": "2026-09-27 02:00", "timezone": "UTC"})

        event_commands.create_event_startgg(event, aws)

        kwargs = mock_event_helper.find_duplicate_event.call_args.kwargs
        self.assertEqual(kwargs["startgg_url"], "https://start.gg/tournament/t/event/e")
        self.assertNotIn("event_name", kwargs)

    @patch("commands.event.event_commands.deferred_dispatch")
    @patch("commands.event.event_commands.startgg_api")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_non_organizer_is_rejected_without_dispatching(
        self, mock_perms, mock_db, mock_event_helper, mock_api, mock_dispatch
    ):
        from commands.models.response_message import ResponseMessage
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_perms.require_organizer_role.return_value = ResponseMessage(content="nope")
        aws = _make_aws()
        event = _make_event(inputs={"event_link": "https://start.gg/tournament/t/event/e",
                                    "end_time": "2026-09-27 02:00", "timezone": "UTC"})

        event_commands.create_event_startgg(event, aws)

        mock_dispatch.dispatch.assert_not_called()


class TestCreateEventDuplicateGuard(unittest.TestCase):
    """A late response makes Discord report failure even though the event was
    created, so organizers re-run the command. The second run must not create a
    second event."""

    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_create_event_refuses_to_duplicate_an_active_event(
        self, mock_perms, mock_db, mock_event_helper, mock_tz, mock_schedule
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_event_helper.find_duplicate_event.return_value = _make_event_data(event_name="Weekly Bracket")
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        result = event_commands.create_event(event, aws)

        mock_event_helper.create_event_record.assert_not_called()
        mock_schedule.sync_schedule.assert_not_called()
        self.assertIn("Weekly Bracket", result.content)
        self.assertIn("/event-update", result.content)

class TestCreateEventHappyPath(unittest.TestCase):
    @patch("commands.event.event_commands.claims")
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_creates_the_event_when_nothing_duplicates_it(
        self, mock_perms, mock_db, mock_event_helper, mock_tz, mock_schedule, mock_claims
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_event_helper.find_duplicate_event.return_value = None
        mock_claims.try_claim_event_create.return_value = True
        mock_tz.to_utc_iso.return_value = "2099-01-01T18:00:00Z"
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket", "event_location": "Online"})

        result = event_commands.create_event(event, aws)

        record = mock_event_helper.create_event_record.call_args.kwargs["record"]
        self.assertEqual(record.name, "Weekly Bracket")
        self.assertEqual(record.start_time_utc, "2099-01-01T18:00:00Z")
        mock_schedule.sync_schedule.assert_called_once()
        self.assertIn("Weekly Bracket", result.content)
        self.assertIn("created successfully", result.content)


class TestCreateEventConcurrencyClaim(unittest.TestCase):
    """The duplicate check reads before it writes. Two invocations racing inside
    that window both see "no duplicate", so the create itself is claimed."""

    @patch("commands.event.event_commands.claims")
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.timezone_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_losing_the_claim_stops_the_create(
        self, mock_perms, mock_db, mock_event_helper, mock_tz, mock_schedule, mock_claims
    ):
        mock_perms.require_organizer_role.return_value = None
        mock_db.get_server_config_or_fail.return_value = _make_server_config()
        mock_event_helper.find_duplicate_event.return_value = None
        mock_claims.try_claim_event_create.return_value = False
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        result = event_commands.create_event(event, aws)

        mock_event_helper.create_event_record.assert_not_called()
        self.assertIn("Weekly Bracket", result.content)

class TestCreateEventClaimRelease(unittest.TestCase):
    """The claim guards only the in-flight window of one create. Left in place it
    would block a delete-then-recreate, or a retry after Discord rejected the
    first attempt, until DynamoDB sweeps it days later."""

    def setUp(self):
        names = ("permissions_helper", "db_helper", "event_helper", "timezone_helper", "schedule_helper", "claims")
        patches = {n: patch(f"commands.event.event_commands.{n}") for n in names}
        self.mocks = {n: p.start() for n, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)
        self.mocks["permissions_helper"].require_organizer_role.return_value = None
        self.mocks["db_helper"].get_server_config_or_fail.return_value = _make_server_config()
        self.mocks["event_helper"].find_duplicate_event.return_value = None
        self.mocks["event_helper"].build_event_identity.return_value = "name:Weekly Bracket|2099-01-01T18:00:00Z"
        self.mocks["timezone_helper"].to_utc_iso.return_value = "2099-01-01T18:00:00Z"
        self.mocks["claims"].try_claim_event_create.return_value = True
        self.aws = _make_aws()
        self.event = _make_event(inputs={"event_name": "Weekly Bracket"})

    def test_claim_is_released_after_a_successful_create(self):
        event_commands.create_event(self.event, self.aws)

        self.mocks["event_helper"].create_event_record.assert_called_once()
        self.mocks["claims"].release_event_create_claim.assert_called_once_with(
            "server123", "name:Weekly Bracket|2099-01-01T18:00:00Z", self.aws.dynamodb_table
        )

    def test_claim_is_released_when_the_create_fails_and_the_error_still_propagates(self):
        # e.g. Discord rejects an end time before the start: bot.py shows the
        # ValueError's text, and the organizer's corrected retry must not be locked out.
        self.mocks["event_helper"].create_event_record.side_effect = ValueError("end before start")

        with self.assertRaisesRegex(ValueError, "end before start"):
            event_commands.create_event(self.event, self.aws)

        self.mocks["claims"].release_event_create_claim.assert_called_once_with(
            "server123", "name:Weekly Bracket|2099-01-01T18:00:00Z", self.aws.dynamodb_table
        )

    def test_a_lost_claim_is_never_released(self):
        # Releasing here would delete the claim of the invocation that is creating.
        self.mocks["claims"].try_claim_event_create.return_value = False

        event_commands.create_event(self.event, self.aws)

        self.mocks["claims"].release_event_create_claim.assert_not_called()


class TestShiftEndTime(unittest.TestCase):
    def test_shifts_end_by_same_delta_as_start(self):
        # Start moves +3h; a 2h event's end should move +3h too, keeping the 2h duration.
        result = event_commands._shift_end_time(
            "2099-01-01T18:00:00Z", "2099-01-01T20:00:00Z", "2099-01-01T21:00:00Z"
        )
        self.assertEqual(result, "2099-01-01T23:00:00Z")

    def test_preserves_duration_when_moved_earlier(self):
        result = event_commands._shift_end_time(
            "2099-01-01T18:00:00Z", "2099-01-01T20:00:00Z", "2099-01-01T15:00:00Z"
        )
        self.assertEqual(result, "2099-01-01T17:00:00Z")

    def test_missing_end_returns_original(self):
        self.assertIsNone(
            event_commands._shift_end_time("2099-01-01T18:00:00Z", None, "2099-01-01T21:00:00Z")
        )

    def test_unparseable_bound_falls_back_to_original_end(self):
        result = event_commands._shift_end_time(
            "garbage", "2099-01-01T20:00:00Z", "2099-01-01T21:00:00Z"
        )
        self.assertEqual(result, "2099-01-01T20:00:00Z")


class TestRefreshEventFromStartgg(unittest.TestCase):
    def _make_startgg_event(self, start_time_utc):
        sg = Mock()
        sg.start_time_utc = start_time_utc
        sg.participants = []
        sg.no_discord_participants = []
        return sg

    @patch("commands.event.event_commands.message_helper")
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.startgg_api")
    def test_reschedule_shifts_end_and_syncs_schedule(
        self, mock_startgg, mock_event_helper, mock_db, mock_schedule, mock_msg
    ):
        mock_msg.get_discord_timestamp.return_value = "<t:123:F>"
        mock_startgg.query_startgg_event.return_value = self._make_startgg_event("2099-01-01T21:00:00Z")
        mock_event_helper.update_event_record.return_value = True
        server_config = _make_server_config()
        mock_db.get_server_config_or_fail.return_value = server_config
        event_data = _make_linked_event_data(start="2099-01-01T18:00:00Z", end="2099-01-01T20:00:00Z")
        aws = _make_aws()

        summary = event_commands.refresh_event_from_startgg("server123", "event_111", event_data, aws)

        # Discord event updated with the new start and an end shifted by the same +3h delta.
        record = mock_event_helper.update_event_record.call_args.kwargs["record"]
        self.assertEqual(record.start_time_utc, "2099-01-01T21:00:00Z")
        self.assertEqual(record.end_time_utc, "2099-01-01T23:00:00Z")
        # The posted schedule message is rebuilt so it doesn't show a stale time.
        mock_schedule.sync_schedule.assert_called_once_with("server123", server_config, aws.dynamodb_table)
        self.assertIn("Start time updated", summary)
        self.assertIn("End time shifted", summary)

    @patch("commands.event.event_commands.message_helper")
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.startgg_api")
    def test_no_start_change_does_not_reschedule(
        self, mock_startgg, mock_event_helper, mock_db, mock_schedule, mock_msg
    ):
        mock_msg.get_discord_timestamp.return_value = "<t:123:F>"
        # start.gg reports the same start time already stored — nothing to reschedule.
        mock_startgg.query_startgg_event.return_value = self._make_startgg_event("2099-01-01T18:00:00Z")
        event_data = _make_linked_event_data(start="2099-01-01T18:00:00Z", end="2099-01-01T20:00:00Z")
        aws = _make_aws()

        summary = event_commands.refresh_event_from_startgg("server123", "event_111", event_data, aws)

        mock_event_helper.update_event_record.assert_not_called()
        mock_schedule.sync_schedule.assert_not_called()
        # Registrants are still synced even when the time is unchanged.
        aws.dynamodb_table.update_item.assert_called_once()
        self.assertIn("Registered list updated", summary)


class TestDeleteEventScheduleRebuild(unittest.TestCase):
    @patch("commands.event.event_commands.schedule_helper")
    @patch("commands.event.event_commands.event_helper")
    @patch("commands.event.event_commands.queue_role_removal")
    @patch("commands.event.event_commands.db_helper")
    @patch("commands.event.event_commands.permissions_helper")
    def test_delete_rebuilds_schedule_instead_of_removing_by_name(
        self, mock_perms, mock_db, mock_queue, mock_event_helper, mock_schedule
    ):
        # Removing the matching line by name deletes every same-named entry, so a
        # duplicate's deletion wiped both. Rebuilding from DynamoDB cannot.
        mock_perms.verify_has_organizer_role.return_value = None
        server_config = _make_server_config()
        mock_db.get_server_config_or_fail.return_value = server_config
        mock_db.get_server_event_data_or_fail.return_value = _make_event_data(event_name="Weekly Bracket")
        aws = _make_aws()
        event = _make_event(inputs={"event_name": "Weekly Bracket"})

        event_commands.delete_event(event, aws)

        mock_schedule.remove_schedule_event.assert_not_called()
        mock_schedule.sync_schedule.assert_called_once_with("server123", server_config, aws.dynamodb_table)


if __name__ == "__main__":
    unittest.main()
