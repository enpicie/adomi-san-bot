import os
import sys

# Scheduled job modules read env vars at import time — set them before importing.
os.environ.setdefault("REGION", "us-east-1")
os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("DYNAMODB_TABLE_NAME", "test-table")
os.environ.setdefault("REMOVE_ROLE_QUEUE_URL", "https://sqs.test")
os.environ.setdefault("STARTGG_OAUTH_SECRET_NAME", "test-secret")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "jobs", "scheduled_job"))

import unittest
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, patch

from event_reminders import check_and_send_reminder

_NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=dt_timezone.utc)
_WITHIN_24H = (_NOW + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
_EXACTLY_24H = (_NOW + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
_BEYOND_24H = (_NOW + timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
_IN_THE_PAST = (_NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_event_record(**overrides):
    base = {
        "event_name": "Test Event",
        "start_time": _WITHIN_24H,
        "should_post_reminder": True,
        "did_post_reminder": False,
    }
    base.update(overrides)
    return base


def _make_server_config(**overrides):
    base = {
        "announcement_channel_id": "channel_123",
        "announcement_role_id": None,
    }
    base.update(overrides)
    return base


class TestCheckAndSendReminder(unittest.TestCase):
    def _run(self, event_record, server_config=None, discord_sent=True):
        """Run check_and_send_reminder with mocked db and discord_api, return (result_config, mock_db, mock_discord)."""
        with patch("event_reminders.db") as mock_db, \
             patch("event_reminders.discord_api") as mock_discord, \
             patch("event_reminders.datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            mock_db.get_event_record.return_value = event_record
            mock_db.get_server_config.return_value = server_config
            mock_discord.send_channel_message.return_value = discord_sent
            result = check_and_send_reminder(Mock(), "server1", "event1", server_config)
        return result, mock_db, mock_discord

    # --- Early-exit gates ---

    def test_returns_unchanged_config_when_event_record_not_found(self):
        with patch("event_reminders.db") as mock_db, patch("event_reminders.discord_api") as mock_discord:
            mock_db.get_event_record.return_value = None
            result = check_and_send_reminder(Mock(), "server1", "event1", None)
        self.assertIsNone(result)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_when_should_post_reminder_is_false(self):
        record = _make_event_record(should_post_reminder=False)
        result, _, mock_discord = self._run(record)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_when_did_post_reminder_is_true(self):
        record = _make_event_record(did_post_reminder=True)
        result, _, mock_discord = self._run(record)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_when_start_time_is_missing(self):
        record = _make_event_record(start_time=None)
        result, _, mock_discord = self._run(record)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_when_event_is_beyond_24h_window(self):
        record = _make_event_record(start_time=_BEYOND_24H)
        result, _, mock_discord = self._run(record)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_when_start_time_is_in_the_past(self):
        record = _make_event_record(start_time=_IN_THE_PAST)
        result, _, mock_discord = self._run(record)
        mock_discord.send_channel_message.assert_not_called()

    def test_skips_at_exactly_24h_boundary(self):
        # The window is exclusive on the upper end (now < start <= now + 24h),
        # so exactly 24h away should still send.
        record = _make_event_record(start_time=_EXACTLY_24H)
        config = _make_server_config()
        result, mock_db, mock_discord = self._run(record, server_config=config)
        mock_discord.send_channel_message.assert_called_once()

    def test_skips_when_no_announcement_channel_configured(self):
        record = _make_event_record()
        config = _make_server_config(announcement_channel_id=None)
        result, mock_db, mock_discord = self._run(record, server_config=config)
        mock_discord.send_channel_message.assert_not_called()

    # --- Happy path ---

    def test_sends_reminder_and_marks_sent_when_all_conditions_met(self):
        record = _make_event_record()
        config = _make_server_config()
        result, mock_db, mock_discord = self._run(record, server_config=config)
        mock_discord.send_channel_message.assert_called_once_with("channel_123", unittest.mock.ANY)
        mock_db.mark_event_reminder_sent.assert_called_once_with(unittest.mock.ANY, "server1", "event1")

    def test_reminder_message_contains_event_name(self):
        record = _make_event_record(event_name="Friday Night Fights")
        config = _make_server_config()
        result, _, mock_discord = self._run(record, server_config=config)
        message = mock_discord.send_channel_message.call_args.args[1]
        self.assertIn("Friday Night Fights", message)

    def test_reminder_message_contains_discord_timestamp(self):
        record = _make_event_record()
        config = _make_server_config()
        result, _, mock_discord = self._run(record, server_config=config)
        message = mock_discord.send_channel_message.call_args.args[1]
        self.assertIn("<t:", message)

    def test_role_ping_prepended_when_announcement_role_set(self):
        record = _make_event_record()
        config = _make_server_config(announcement_role_id="role_999")
        result, _, mock_discord = self._run(record, server_config=config)
        message = mock_discord.send_channel_message.call_args.args[1]
        self.assertTrue(message.startswith("<@&role_999>"))

    def test_no_role_ping_when_announcement_role_not_set(self):
        record = _make_event_record()
        config = _make_server_config(announcement_role_id=None)
        result, _, mock_discord = self._run(record, server_config=config)
        message = mock_discord.send_channel_message.call_args.args[1]
        self.assertNotIn("<@&", message)

    def test_does_not_mark_sent_when_discord_send_fails(self):
        record = _make_event_record()
        config = _make_server_config()
        result, mock_db, _ = self._run(record, server_config=config, discord_sent=False)
        mock_db.mark_event_reminder_sent.assert_not_called()

    # --- Server config lazy loading ---

    def test_loads_server_config_from_db_when_not_cached(self):
        record = _make_event_record()
        fetched_config = _make_server_config()
        with patch("event_reminders.db") as mock_db, \
             patch("event_reminders.discord_api"), \
             patch("event_reminders.datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            mock_db.get_event_record.return_value = record
            mock_db.get_server_config.return_value = fetched_config
            result = check_and_send_reminder(Mock(), "server1", "event1", None)
        mock_db.get_server_config.assert_called_once()
        self.assertEqual(result, fetched_config)

    def test_skips_db_config_fetch_when_already_cached(self):
        record = _make_event_record()
        cached_config = _make_server_config()
        with patch("event_reminders.db") as mock_db, \
             patch("event_reminders.discord_api"), \
             patch("event_reminders.datetime") as mock_dt:
            mock_dt.now.return_value = _NOW
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            mock_db.get_event_record.return_value = record
            check_and_send_reminder(Mock(), "server1", "event1", cached_config)
        mock_db.get_server_config.assert_not_called()

    def test_returns_server_config_to_caller_for_caching(self):
        record = _make_event_record()
        config = _make_server_config()
        result, _, _ = self._run(record, server_config=config)
        self.assertEqual(result, config)


if __name__ == "__main__":
    unittest.main()
