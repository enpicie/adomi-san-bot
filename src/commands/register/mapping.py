from discord import AppCommandOptionType

import commands.register.register_constants as register_constants
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.register.register_list_commands as register_list_commands
import commands.register.register_commands as register_commands
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

register_commands_mapping: CommandMapping = {
    "register-list": {
        "function": register_list_commands.show_registered,
        "description": "Show list of registered users for an event",
        "params": [EVENT_NAME_PARAM]
    },
    "register-clear": {
        "function": register_list_commands.clear_registered,
        "description": "Clear list of registered users for an event",
        "params": [EVENT_NAME_PARAM]
    },
    "register": {
        "function": register_commands.register_user,
        "description": "Register yourself for an event, or register another user (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="(Organizer only) Register this user for the event instead of yourself",
                param_type=AppCommandOptionType.user,
                required=False,
                choices=None
            )
        ]
    },
    "register-remove": {
        "function": register_commands.register_remove,
        "description": "Remove a user from an event's registered list (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="The user to remove from the registered list",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            )
        ]
    },
    "register-toggle": {
        "function": register_commands.toggle_register,
        "description": "Toggle registration start/end to set if registrations are accepted or rejected (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="state",
                description="Set to 'Start' to begin accepting registrations, and set to 'End' to reject further registrations",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(name="Start", value=register_constants.START_PARAM),
                    ParamChoice(name="End", value=register_constants.END_PARAM)
                ]
            )
        ]
    }
}
