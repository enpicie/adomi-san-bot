import os
import sys

# Scheduled job modules read env vars at import time (via scheduled_job_constants).
# Assign deterministic test values directly so real host env vars never leak through.
os.environ["REGION"] = "us-east-1"
os.environ["DISCORD_BOT_TOKEN_SECRET_NAME"] = "test-secret-name"
os.environ["DYNAMODB_TABLE_NAME"] = "test-table"
os.environ["REMOVE_ROLE_QUEUE_URL"] = "https://sqs.test"
os.environ["STARTGG_SECRET_NAME"] = "test-startgg-secret"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "scheduled_job"))

import unittest
from unittest.mock import Mock, patch

from event_reschedule_check import check_for_reschedule

# Far-future / far-past so the past-time guard is deterministic regardless of wall-clock time.
_STORED_START = "2099-04-10T18:00:00Z"
_NEW_START = "2099-04-10T21:00:00Z"
_PAST_START = "2000-01-01T00:00:00Z"


def _make_event_record(**overrides):
    base = {
        "event_name": "Test Event",
        "start_time": _STORED_START,
        "startgg_url": "https://www.start.gg/tournament/t/event/e",
    }
    base.update(overrides)
    return base


def _make_server_config(**overrides):
    base = {
        "notification_channel_id": "channel_123",
        "organizer_role": "role_9",
        "ping_organizers": False,
    }
    base.update(overrides)
    return base


class TestCheckForReschedule(unittest.TestCase):
    def _run(self, event_record, server_config=None, startgg_start=_NEW_START):
        with patch("event_reschedule_check.db") as mock_db, \
             patch("event_reschedule_check.discord_api") as mock_discord, \
             patch("event_reschedule_check.startgg_api") as mock_startgg:
            mock_db.get_event_record.return_value = event_record
            mock_startgg.get_event_start_time_utc.return_value = startgg_start
            check_for_reschedule(Mock(), "server1", "event1", server_config)
        return mock_db, mock_discord, mock_startgg

    # --- Early-exit gates ---
    def test_missing_event_record_does_nothing(self):
        mock_db, mock_discord, mock_startgg = self._run(None)
        mock_startgg.get_event_start_time_utc.assert_not_called()
        mock_discord.send_organizer_notification.assert_not_called()

    def test_no_startgg_url_does_not_query(self):
        mock_db, mock_discord, mock_startgg = self._run(_make_event_record(startgg_url=None))
        mock_startgg.get_event_start_time_utc.assert_not_called()
        mock_discord.send_organizer_notification.assert_not_called()

    def test_startgg_query_failure_does_not_alert(self):
        mock_db, mock_discord, mock_startgg = self._run(_make_event_record(), startgg_start=None)
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_reschedule_alerted.assert_not_called()

    # --- No drift ---
    def test_matching_time_with_no_marker_is_noop(self):
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(), server_config=_make_server_config(), startgg_start=_STORED_START
        )
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.clear_reschedule_alerted.assert_not_called()

    def test_matching_time_clears_stale_marker(self):
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(reschedule_alerted_start=_NEW_START),
            server_config=_make_server_config(),
            startgg_start=_STORED_START,
        )
        mock_db.clear_reschedule_alerted.assert_called_once_with(unittest.mock.ANY, "server1", "event1")
        mock_discord.send_organizer_notification.assert_not_called()

    # --- Drift detected ---
    def test_drift_alerts_and_marks(self):
        config = _make_server_config()
        mock_db, mock_discord, mock_startgg = self._run(_make_event_record(), server_config=config)
        mock_discord.send_organizer_notification.assert_called_once()
        call = mock_discord.send_organizer_notification.call_args
        self.assertEqual(call.args[0], "channel_123")
        self.assertIn("rescheduled", call.args[1])
        self.assertIn("/event-refresh-startgg", call.args[1])
        self.assertEqual(call.kwargs["organizer_role"], "role_9")
        mock_db.mark_reschedule_alerted.assert_called_once_with(
            unittest.mock.ANY, "server1", "event1", _NEW_START
        )

    def test_drift_already_alerted_for_same_time_does_not_realert(self):
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(reschedule_alerted_start=_NEW_START),
            server_config=_make_server_config(),
        )
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_reschedule_alerted.assert_not_called()

    def test_drift_alerted_for_different_time_realerts(self):
        # start.gg moved to a *new* time since the last alert — re-arm and notify again.
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(reschedule_alerted_start="2026-04-10T20:00:00Z"),
            server_config=_make_server_config(),
        )
        mock_discord.send_organizer_notification.assert_called_once()
        mock_db.mark_reschedule_alerted.assert_called_once_with(
            unittest.mock.ANY, "server1", "event1", _NEW_START
        )

    def test_drift_to_past_time_does_not_alert(self):
        # start.gg drifted to a past time; /event-refresh-startgg would refuse to apply it, so the
        # poller stays quiet rather than sending a dead-end alert.
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(), server_config=_make_server_config(), startgg_start=_PAST_START
        )
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_reschedule_alerted.assert_not_called()

    def test_matching_past_time_still_clears_marker(self):
        # An event already underway (stored start in the past) with start.gg matching: no drift,
        # and any stale marker is cleared. The past-time guard must not pre-empt this.
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(start_time=_PAST_START, reschedule_alerted_start=_NEW_START),
            server_config=_make_server_config(),
            startgg_start=_PAST_START,
        )
        mock_db.clear_reschedule_alerted.assert_called_once_with(unittest.mock.ANY, "server1", "event1")
        mock_discord.send_organizer_notification.assert_not_called()

    def test_drift_without_notification_channel_does_not_mark(self):
        mock_db, mock_discord, mock_startgg = self._run(
            _make_event_record(), server_config=_make_server_config(notification_channel_id=None)
        )
        mock_discord.send_organizer_notification.assert_not_called()
        # Marker left unset so the alert fires once a channel is configured.
        mock_db.mark_reschedule_alerted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
