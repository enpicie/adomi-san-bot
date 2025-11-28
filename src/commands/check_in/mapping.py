from discord import AppCommandOptionType

import commands.check_in.check_in_constants as check_in_constants
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.check_in.check_in_commands as check_in_commands

checkin_commands: CommandMapping = {
    "check-in": {
        "function": check_in_commands.check_in_user,
        "description": "Check in the calling user and assign Participant role if set",
        "params": []
    },
    "show-check-ins": {
        "function": check_in_commands.show_checked_in,
        "description": "Show list of checked-in users",
        "params": []
    },
    "clear-check-ins": {
        "function": check_in_commands.clear_checked_in,
        "description": "Clear list of checked-in users and remove Participant roles if set",
        "params": []
    },
    "show-not-checked-in": {
        "function": check_in_commands.show_not_checked_in,
        "description": "Show list of users who are registered but not checked-in and optionally ping them",
        "params": [
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
    "toggle-check-in": {
        "function": check_in_commands.toggle_check_in,
        "description": "Toggle check-in start/end to set if check-ins are accepted or rejected",
        "params": [
            CommandParam(
                name = "state",
                description = "Set to 'Start' to begin accepting check-ins, and set ot 'End' to reject further check-ins",
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
