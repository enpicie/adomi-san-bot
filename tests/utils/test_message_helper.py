import unittest

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
