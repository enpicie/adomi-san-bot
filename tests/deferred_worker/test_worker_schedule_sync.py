"""jobs/deferred_worker/worker_schedule_sync.py — MIRROR of src sync_schedule."""
import unittest
from unittest.mock import Mock, patch

import worker_schedule_sync as schedule_sync

_CONFIG = {"schedule_message_id": "msg1", "schedule_channel_id": "chan1"}


class TestSyncSchedule(unittest.TestCase):
    def setUp(self):
        patches = {n: patch.object(schedule_sync, n) for n in ("discord_api", "db_helper")}
        self.mocks = {n: p.start() for n, p in patches.items()}
        for p in patches.values():
            self.addCleanup(p.stop)
        self.mocks["db_helper"].get_full_events_for_server.return_value = []
        self.mocks["db_helper"].get_schedule_plans_for_server.return_value = []
        self.mocks["discord_api"].edit_channel_message.return_value = True

    def test_unreadable_message_is_still_rebuilt_under_the_default_title(self):
        # src falls back to DEFAULT_SCHEDULE_TITLE and still edits the message;
        # skipping would leave the schedule showing the pre-create state.
        self.mocks["discord_api"].get_channel_message.return_value = None

        schedule_sync.sync_schedule("server123", _CONFIG, Mock())

        self.mocks["discord_api"].edit_channel_message.assert_called_once()
        content = self.mocks["discord_api"].edit_channel_message.call_args.args[2]
        self.assertTrue(content.startswith(f"# {schedule_sync.DEFAULT_SCHEDULE_TITLE}\n"))

    def test_existing_title_is_kept(self):
        self.mocks["discord_api"].get_channel_message.return_value = "# Friday Night Fights\n\n*No events.*"

        schedule_sync.sync_schedule("server123", _CONFIG, Mock())

        content = self.mocks["discord_api"].edit_channel_message.call_args.args[2]
        self.assertTrue(content.startswith("# Friday Night Fights\n"))

    def test_superseded_plan_is_deleted_by_its_display_name(self):
        # The db helper normalizes (see test_db_helper); the sync passes the
        # plan's display name through unchanged.
        self.mocks["discord_api"].get_channel_message.return_value = "# Upcoming Events"
        self.mocks["db_helper"].get_full_events_for_server.return_value = [{"event_name": "Weekly Bracket"}]
        self.mocks["db_helper"].get_schedule_plans_for_server.return_value = [{"plan_name": "Weekly Bracket"}]
        table = Mock()

        schedule_sync.sync_schedule("server123", _CONFIG, table)

        self.mocks["db_helper"].delete_schedule_plan.assert_called_once_with("server123", "Weekly Bracket", table)


if __name__ == "__main__":
    unittest.main()
