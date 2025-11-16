from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.setup.server_commands as server_commands

setup_commands: CommandMapping = {
    "setup-server": {
        "function": server_commands.setup_server,
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
        "function": server_commands.set_organizer_role,
        "description": "Set the role for event organizers who can use privileged commands.",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    }
}
