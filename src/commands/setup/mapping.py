from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.setup.server_config_commands as server_config_commands
import commands.setup.event_data_commands as event_data_commands

setup_commands: CommandMapping = {
    "setup-server": {
        "function": server_config_commands.setup_server,
        "description": "Set up this server for use with the bot.",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    },
    "set-organizer-role": {
        "function": server_config_commands.set_organizer_role,
        "description": "Set the role for event organizers who can use privileged commands",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    },
    "set-participant-role": {
        "function": event_data_commands.set_participant_role,
        "description": "Set the role for event participants to be pinged during events",
        "params": [
            CommandParam(
                name="participant_role",
                description="Role for event participants to be pinged during events",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            ),
            CommandParam(
                name="remove_role",
                description="Set to 'Yes' to remove the participant role instead of setting it (default: No)",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="Yes", value=True),
                    ParamChoice(name="No", value=False)
                ]
            )
        ]
    }
}
