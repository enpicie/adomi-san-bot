"""jobs/deferred_worker/timezone_helper.py — MIRROR of src/commands/event/timezone_helper.py."""
import unittest

import timezone_helper as worker_timezone_helper

import commands.event.timezone_helper as src_timezone_helper


class TestWorkerTimezoneHelperMirror(unittest.TestCase):
    def test_converts_like_the_src_twin(self):
        self.assertEqual(
            worker_timezone_helper.to_utc_iso("2026-01-15 15:00", "Eastern Time (US)"),
            src_timezone_helper.to_utc_iso("2026-01-15 15:00", "Eastern Time (US)"),
        )

    def test_unknown_timezone_message_matches_src(self):
        with self.assertRaises(worker_timezone_helper.InvalidTimeInputError) as ctx:
            worker_timezone_helper.to_utc_iso("2026-03-19 19:30", "Central")
        self.assertEqual(str(ctx.exception), src_timezone_helper.INVALID_TIMEZONE_MESSAGE)

    def test_bad_format_message_matches_src(self):
        with self.assertRaises(worker_timezone_helper.InvalidTimeInputError) as ctx:
            worker_timezone_helper.to_utc_iso("tomorrow at 7", "UTC")
        self.assertEqual(str(ctx.exception), src_timezone_helper.INVALID_DATETIME_MESSAGE)


if __name__ == "__main__":
    unittest.main()
