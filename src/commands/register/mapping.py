from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
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
        "description": "Register yourself for an event",
        "params": [EVENT_NAME_PARAM]
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
    }
}
