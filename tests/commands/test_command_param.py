import unittest

from discord import AppCommandOptionType

from commands.models.command_param import CommandParam, ParamChoice


class TestCommandParamToDict(unittest.TestCase):
    def _make_param(self, **overrides) -> CommandParam:
        defaults = dict(
            name="my_param",
            description="A test parameter",
            param_type=AppCommandOptionType.string,
            required=True,
            choices=None,
        )
        defaults.update(overrides)
        return CommandParam(**defaults)

    def test_required_fields_present(self):
        result = self._make_param().to_dict()
        self.assertEqual(result["name"], "my_param")
        self.assertEqual(result["description"], "A test parameter")
        self.assertEqual(result["type"], AppCommandOptionType.string.value)
        self.assertTrue(result["required"])

    def test_autocomplete_defaults_to_false(self):
        self.assertFalse(self._make_param().to_dict()["autocomplete"])

    def test_autocomplete_true_is_included(self):
        self.assertTrue(self._make_param(autocomplete=True).to_dict()["autocomplete"])

    def test_optional_param(self):
        self.assertFalse(self._make_param(required=False).to_dict()["required"])

    def test_choices_included_when_present(self):
        param = self._make_param(choices=[
            ParamChoice(name="Option A", value="a"),
            ParamChoice(name="Option B", value="b"),
        ])
        result = param.to_dict()
        self.assertIn("choices", result)
        self.assertEqual(result["choices"], [
            {"name": "Option A", "value": "a"},
            {"name": "Option B", "value": "b"},
        ])

    def test_choices_absent_when_none(self):
        self.assertNotIn("choices", self._make_param(choices=None).to_dict())

    def test_integer_param_type_value(self):
        result = self._make_param(param_type=AppCommandOptionType.integer).to_dict()
        self.assertEqual(result["type"], AppCommandOptionType.integer.value)

    def test_boolean_choice_value_serialized(self):
        # ParamChoice.value is Any; booleans used for boolean-type options must survive to_dict
        param = self._make_param(choices=[ParamChoice(name="Yes", value=True)])
        self.assertEqual(param.to_dict()["choices"][0]["value"], True)


if __name__ == "__main__":
    unittest.main()
