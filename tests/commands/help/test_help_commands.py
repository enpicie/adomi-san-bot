import unittest
from unittest.mock import Mock

from commands.help.adomi_help_commands import give_help, help_check_in, help_register, help_event
from commands.models.response_message import ResponseMessage


def _make_event():
    return Mock()


def _make_aws():
    return Mock()


class TestGiveHelp(unittest.TestCase):
    def test_returns_response_message(self):
        result = give_help(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)

    def test_content_mentions_check_in(self):
        result = give_help(_make_event(), _make_aws())
        self.assertIn("check-in", result.content)


class TestHelpCheckIn(unittest.TestCase):
    def test_returns_response_message(self):
        result = help_check_in(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)

    def test_lists_check_in_commands(self):
        result = help_check_in(_make_event(), _make_aws())
        self.assertIn("/check-in", result.content)
        self.assertIn("/check-in-toggle", result.content)
        self.assertIn("/check-in-list", result.content)

    def test_includes_descriptions(self):
        result = help_check_in(_make_event(), _make_aws())
        self.assertIn("—", result.content)

    def test_header_present(self):
        result = help_check_in(_make_event(), _make_aws())
        self.assertIn("Check-in Commands", result.content)


class TestHelpRegister(unittest.TestCase):
    def test_returns_response_message(self):
        result = help_register(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)

    def test_lists_register_commands(self):
        result = help_register(_make_event(), _make_aws())
        self.assertIn("/register", result.content)
        self.assertIn("/register-toggle", result.content)
        self.assertIn("/register-list", result.content)
        self.assertIn("/register-remove", result.content)

    def test_includes_descriptions(self):
        result = help_register(_make_event(), _make_aws())
        self.assertIn("—", result.content)

    def test_header_present(self):
        result = help_register(_make_event(), _make_aws())
        self.assertIn("Register Commands", result.content)


class TestHelpEvent(unittest.TestCase):
    def test_returns_response_message(self):
        result = help_event(_make_event(), _make_aws())
        self.assertIsInstance(result, ResponseMessage)

    def test_lists_event_commands(self):
        result = help_event(_make_event(), _make_aws())
        self.assertIn("/event-create", result.content)
        self.assertIn("/event-list", result.content)
        self.assertIn("/event-delete", result.content)

    def test_includes_descriptions(self):
        result = help_event(_make_event(), _make_aws())
        self.assertIn("—", result.content)

    def test_header_present(self):
        result = help_event(_make_event(), _make_aws())
        self.assertIn("Event Commands", result.content)


if __name__ == "__main__":
    unittest.main()
