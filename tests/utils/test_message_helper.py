import unittest
from datetime import datetime, timezone as dt_timezone

import utils.message_helper as message_helper
from database.models.participant import Participant


def _p(user_id: str, display_name: str) -> dict:
    """Build a participant dict as it would come from DynamoDB."""
    return {
        Participant.Keys.USER_ID: user_id,
        Participant.Keys.DISPLAY_NAME: display_name,
    }


class TestFormatHelpers(unittest.TestCase):
    def test_get_user_ping(self):
        self.assertEqual(message_helper.get_user_ping("123"), "<@123>")

    def test_get_channel_mention(self):
        self.assertEqual(message_helper.get_channel_mention("456"), "<#456>")

    def test_get_role_ping(self):
        self.assertEqual(message_helper.get_role_ping("789"), "<@&789>")


class TestGetDiscordTimestamp(unittest.TestCase):
    ISO = "2026-04-10T12:00:00Z"
    # Epoch computed from the same fixed instant — no real "now" involved.
    EPOCH = int(datetime(2026, 4, 10, 12, 0, 0, tzinfo=dt_timezone.utc).timestamp())

    def test_known_iso_string_returns_full_style_tag_by_default(self):
        self.assertEqual(
            message_helper.get_discord_timestamp(self.ISO),
            f"<t:{self.EPOCH}:F>",
        )

    def test_style_param_is_honored(self):
        self.assertEqual(
            message_helper.get_discord_timestamp(self.ISO, style="R"),
            f"<t:{self.EPOCH}:R>",
        )

    def test_explicit_utc_offset_parses_same_as_z_suffix(self):
        self.assertEqual(
            message_helper.get_discord_timestamp("2026-04-10T12:00:00+00:00"),
            f"<t:{self.EPOCH}:F>",
        )

    def test_garbage_string_returns_none(self):
        self.assertIsNone(message_helper.get_discord_timestamp("not-a-date"))

    def test_none_input_returns_none(self):
        self.assertIsNone(message_helper.get_discord_timestamp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(message_helper.get_discord_timestamp(""))


class TestBuildParticipantsList(unittest.TestCase):
    HEADER = "Attendees"

    def test_empty_list(self):
        result = message_helper.build_participants_list(self.HEADER, [])
        self.assertEqual(result, "Attendees\nNo participants")

    def test_single_discord_user(self):
        result = message_helper.build_participants_list(self.HEADER, [_p("100", "Alice")])
        self.assertEqual(result, "Attendees\n1. <@100>: Alice")

    def test_discord_users_sorted_alphabetically(self):
        participants = [_p("200", "Zed"), _p("100", "Alice"), _p("300", "Bob")]
        result = message_helper.build_participants_list(self.HEADER, participants)
        self.assertEqual(result, "Attendees\n1. <@100>: Alice\n2. <@300>: Bob\n3. <@200>: Zed")

    def test_placeholder_user_has_no_ping(self):
        participants = [_p(Participant.DEFAULT_ID_PLACEHOLDER, "Guest A")]
        result = message_helper.build_participants_list(self.HEADER, participants)
        self.assertEqual(result, "Attendees\n1. Guest A *(no Discord linked)*")

    def test_placeholder_users_sorted(self):
        participants = [
            _p(Participant.DEFAULT_ID_PLACEHOLDER, "Guest Z"),
            _p(Participant.DEFAULT_ID_PLACEHOLDER, "Guest A"),
        ]
        result = message_helper.build_participants_list(self.HEADER, participants)
        self.assertEqual(result, "Attendees\n1. Guest A *(no Discord linked)*\n2. Guest Z *(no Discord linked)*")

    def test_mixed_discord_and_placeholder_sorted(self):
        participants = [
            _p("400", "Dave"),
            _p(Participant.DEFAULT_ID_PLACEHOLDER, "External"),
            _p("300", "Charlie"),
            _p("500", "Adam"),
        ]
        result = message_helper.build_participants_list(self.HEADER, participants)
        self.assertEqual(
            result,
            "Attendees\n1. <@500>: Adam\n2. <@300>: Charlie\n3. <@400>: Dave\n4. External *(no Discord linked)*"
        )


if __name__ == "__main__":
    unittest.main()
