import unittest
from unittest.mock import Mock, patch

import bot
from commands.models.command_param import CommandParam
from commands.models.response_message import ResponseMessage
from discord import AppCommandOptionType


def _event_body(command_name: str = "test-cmd") -> dict:
    """Minimal valid Discord slash-command event body."""
    return {
        "data": {"name": command_name, "options": []},
        "guild_id": "SERVER123",
        "channel_id": "CHAN456",
        "member": {
            "user": {"id": "U1", "username": "tester"},
            "permissions": "32",
            "roles": [],
        },
    }


def _autocomplete_body(command_name: str, focused_name: str, value: str = "par") -> dict:
    return {
        "data": {
            "name": command_name,
            "options": [{"name": focused_name, "value": value, "focused": True}],
        },
        "guild_id": "SERVER123",
        "member": {
            "user": {"id": "U1", "username": "tester"},
            "permissions": "0",
            "roles": [],
        },
    }


class TestProcessBotCommand(unittest.TestCase):
    def setUp(self):
        self.aws = Mock()
        self.mock_fn = Mock(return_value=ResponseMessage(content="OK"))
        self.command = {"function": self.mock_fn, "params": []}

    def test_routes_to_correct_command_function(self):
        with patch.dict("bot.command_map", {"test-cmd": self.command}):
            result = bot.process_bot_command(_event_body("test-cmd"), self.aws)
        self.mock_fn.assert_called_once()
        self.assertEqual(result["type"], 4)  # MESSAGE_WITH_SOURCE

    def test_raises_value_error_for_unknown_command(self):
        with patch.dict("bot.command_map", {}):
            with self.assertRaises(ValueError):
                bot.process_bot_command(_event_body("unknown"), self.aws)

    def test_raises_key_error_when_data_field_missing(self):
        with self.assertRaises(KeyError):
            bot.process_bot_command({}, self.aws)

    def test_returns_generic_error_response_when_command_raises(self):
        self.mock_fn.side_effect = RuntimeError("boom")
        with patch.dict("bot.command_map", {"test-cmd": self.command}):
            result = bot.process_bot_command(_event_body("test-cmd"), self.aws)
        # Must not re-raise — returns an error ResponseMessage instead
        self.assertEqual(result["type"], 4)
        self.assertIn("Something went wrong", result["data"]["content"])


class TestProcessInputAutocomplete(unittest.TestCase):
    def setUp(self):
        self.aws = Mock()

    def _make_param_with_handler(self, name: str, handler: Mock) -> CommandParam:
        return CommandParam(
            name=name,
            description="desc",
            param_type=AppCommandOptionType.string,
            required=True,
            choices=None,
            autocomplete=True,
            autocomplete_handler=handler,
        )

    def test_calls_handler_for_focused_option(self):
        handler = Mock()
        handler.return_value = Mock(to_dict=lambda: {"type": 8, "data": {"choices": []}})
        param = self._make_param_with_handler("my_opt", handler)
        command = {"function": Mock(), "params": [param]}

        with patch.dict("bot.command_map", {"my-cmd": command}):
            result = bot.process_input_autocomplete(
                _autocomplete_body("my-cmd", "my_opt"), self.aws
            )

        handler.assert_called_once()
        self.assertEqual(result["type"], 8)

    def test_raises_key_error_when_data_field_missing(self):
        with self.assertRaises(KeyError):
            bot.process_input_autocomplete({}, self.aws)

    def test_raises_key_error_when_no_focused_option(self):
        body = {
            "data": {"name": "my-cmd", "options": [{"name": "x", "value": "y"}]},
            "guild_id": "S1",
            "member": {"user": {"id": "U1", "username": "t"}, "permissions": "0", "roles": []},
        }
        with patch.dict("bot.command_map", {"my-cmd": {"function": Mock(), "params": []}}):
            with self.assertRaises(KeyError):
                bot.process_input_autocomplete(body, self.aws)

    def test_raises_value_error_for_unknown_command(self):
        with patch.dict("bot.command_map", {}):
            with self.assertRaises(ValueError):
                bot.process_input_autocomplete(_autocomplete_body("unknown", "x"), self.aws)


if __name__ == "__main__":
    unittest.main()
