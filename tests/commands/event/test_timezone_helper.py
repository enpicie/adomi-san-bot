import unittest

import commands.event.timezone_helper as timezone_helper
from commands.event.timezone_helper import InvalidTimeInputError, to_utc_iso


class TestToUtcIso(unittest.TestCase):
    def test_utc_passthrough(self):
        self.assertEqual(to_utc_iso("2026-03-19 12:00", "UTC"), "2026-03-19T12:00:00Z")

    def test_eastern_standard_time(self):
        # January → EST (UTC-5): 15:00 + 5h = 20:00 UTC
        self.assertEqual(to_utc_iso("2026-01-15 15:00", "America/New_York"), "2026-01-15T20:00:00Z")

    def test_eastern_daylight_time(self):
        # July → EDT (UTC-4): 12:00 + 4h = 16:00 UTC
        self.assertEqual(to_utc_iso("2026-07-04 12:00", "America/New_York"), "2026-07-04T16:00:00Z")

    def test_pacific_daylight_time(self):
        # July → PDT (UTC-7): 20:00 + 7h = 03:00 UTC next day
        self.assertEqual(to_utc_iso("2026-07-04 20:00", "America/Los_Angeles"), "2026-07-05T03:00:00Z")

    def test_japan_standard_time_no_dst(self):
        # JST (UTC+9, no DST): 09:00 - 9h = 00:00 UTC
        self.assertEqual(to_utc_iso("2026-01-01 09:00", "Asia/Tokyo"), "2026-01-01T00:00:00Z")

    def test_midnight_rolls_over_to_previous_day(self):
        # JST midnight: 2026-05-01 00:30 - 9h = 2026-04-30 15:30 UTC
        self.assertEqual(to_utc_iso("2026-05-01 00:30", "Asia/Tokyo"), "2026-04-30T15:30:00Z")

    def test_output_format_is_iso_8601(self):
        result = to_utc_iso("2026-06-15 10:00", "UTC")
        self.assertRegex(result, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


    def test_display_name_from_autocomplete_repopulation_still_converts(self):
        self.assertEqual(to_utc_iso("2026-01-15 15:00", "Eastern Time (US)"), "2026-01-15T20:00:00Z")


class TestToUtcIsoRejectsUnreadableInput(unittest.TestCase):
    """The message is what the organizer sees (bot.py shows a ValueError's text)."""

    def test_typed_timezone_that_is_not_a_known_zone(self):
        with self.assertRaises(InvalidTimeInputError) as ctx:
            to_utc_iso("2026-03-19 19:30", "Central")
        self.assertEqual(str(ctx.exception), timezone_helper.INVALID_TIMEZONE_MESSAGE)

    def test_wrong_datetime_format_names_the_expected_format(self):
        with self.assertRaises(InvalidTimeInputError) as ctx:
            to_utc_iso("12/01/2026 7:30 PM", "America/Chicago")
        self.assertEqual(str(ctx.exception), timezone_helper.INVALID_DATETIME_MESSAGE)
        self.assertIn("2026-03-19 19:30", str(ctx.exception))
        self.assertNotIn("%Y", str(ctx.exception))

    def test_is_a_value_error_so_the_bot_shows_its_message(self):
        self.assertTrue(issubclass(InvalidTimeInputError, ValueError))


if __name__ == "__main__":
    unittest.main()
