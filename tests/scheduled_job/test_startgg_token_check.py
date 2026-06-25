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

from startgg_token_check import check_startgg_tokens

_NOW = 1_700_000_000
_HOUR = 3600


def _make_config(**overrides):
    base = {
        "server_id": "server1",
        "startgg_token_expires_at": _NOW + 48 * _HOUR,
        "notification_channel_id": "channel_123",
        "organizer_role": "role_456",
        "ping_organizers": True,
    }
    base.update(overrides)
    return base


class TestCheckStartggTokens(unittest.TestCase):
    def _run(self, configs):
        """Run check_startgg_tokens with mocked db, discord_api, and time; return (mock_db, mock_discord)."""
        with patch("startgg_token_check.db") as mock_db, \
             patch("startgg_token_check.discord_api") as mock_discord, \
             patch("startgg_token_check.time") as mock_time:
            mock_time.time.return_value = _NOW
            mock_db.get_all_server_configs_with_oauth.return_value = configs
            check_startgg_tokens(Mock())
        return mock_db, mock_discord

    def test_no_servers_does_nothing(self):
        mock_db, mock_discord = self._run([])
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_startgg_expiry_notified.assert_not_called()

    def test_token_valid_no_notification(self):
        mock_db, mock_discord = self._run([_make_config()])
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_startgg_expiry_notified.assert_not_called()
        mock_db.clear_startgg_expiry_notified.assert_not_called()

    def test_token_valid_after_relink_rearms_notification(self):
        mock_db, mock_discord = self._run([_make_config(startgg_expiry_notified=True)])
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.clear_startgg_expiry_notified.assert_called_once()
        self.assertEqual(mock_db.clear_startgg_expiry_notified.call_args.args[1], "server1")

    def test_expiring_soon_notifies_and_marks(self):
        mock_db, mock_discord = self._run([_make_config(startgg_token_expires_at=_NOW + 12 * _HOUR)])
        mock_discord.send_organizer_notification.assert_called_once()
        args, kwargs = mock_discord.send_organizer_notification.call_args
        self.assertEqual(args[0], "channel_123")
        self.assertIn("expire soon", args[1])
        self.assertEqual(kwargs["organizer_role"], "role_456")
        self.assertTrue(kwargs["ping_organizers"])
        mock_db.mark_startgg_expiry_notified.assert_called_once()
        self.assertEqual(mock_db.mark_startgg_expiry_notified.call_args.args[1], "server1")

    def test_expired_notifies_with_expired_wording(self):
        mock_db, mock_discord = self._run([_make_config(startgg_token_expires_at=_NOW - _HOUR)])
        args, _ = mock_discord.send_organizer_notification.call_args
        self.assertIn("expired", args[1])
        mock_db.mark_startgg_expiry_notified.assert_called_once()

    def test_already_notified_does_not_renotify(self):
        mock_db, mock_discord = self._run(
            [_make_config(startgg_token_expires_at=_NOW - _HOUR, startgg_expiry_notified=True)]
        )
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_startgg_expiry_notified.assert_not_called()

    def test_no_notification_channel_skips(self):
        mock_db, mock_discord = self._run(
            [_make_config(startgg_token_expires_at=_NOW - _HOUR, notification_channel_id=None)]
        )
        mock_discord.send_organizer_notification.assert_not_called()
        mock_db.mark_startgg_expiry_notified.assert_not_called()


if __name__ == "__main__":
    unittest.main()
