from discord import AppCommandOptionType

import commands.check_in.check_in_constants as check_in_constants
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.check_in.check_in_commands as check_in_commands
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

checkin_commands: CommandMapping = {
    "check-in": {
        "function": check_in_commands.check_in_user,
        "description": "Check in the calling user and assign Participant role if set",
        "params": [EVENT_NAME_PARAM]
    },
    "check-in-list": {
        "function": check_in_commands.show_checked_in,
        "description": "Show list of checked-in users (Organizer only)",
        "params": [EVENT_NAME_PARAM]
    },
    "check-in-clear": {
        "function": check_in_commands.clear_checked_in,
        "description": "Clear list of checked-in users and remove Participant roles if set (Organizer only)",
        "params": [EVENT_NAME_PARAM]
    },
    "check-in-list-absent": {
        "function": check_in_commands.show_not_checked_in,
        "description": "Show registered users who have not checked in, optionally ping them (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name = "ping_users",
                description = "Set to 'True' to ping registered users who have not yet checked in (default: 'False')",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False)
                ]
            )
        ]
    },
    "check-in-remove": {
        "function": check_in_commands.remove_checked_in,
        "description": "Remove a user from check-in and queue participant role removal if set (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="The user to remove from check-in",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            )
        ]
    },
    "check-in-toggle": {
        "function": check_in_commands.toggle_check_in,
        "description": "Open or close check-ins for an event (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name = "state",
                description = "Set to 'Start' to begin accepting check-ins, and set to 'End' to reject further check-ins",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(name="Start", value=check_in_constants.START_PARAM),
                    ParamChoice(name="End", value=check_in_constants.END_PARAM)
                ]
            )
        ]
    }
}
