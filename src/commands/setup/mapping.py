from discord import AppCommandOptionType

from enums import EventMode
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.setup.server_commands as server_commands

setup_commands: CommandMapping = {
    "setup-server": {
        "function": server_commands.setup_server,
        "description": "Set up this server for use with the bot.",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            )
        ]
    },
    # TODO: Uncomment when event-mode functionality is enabled again.
    # "setup-event-mode": {
    #     "function": server_commands.setup_event_mode,
    #     "description": "Set event-mode for how bot will manage event data.",
    #     "params": [
    #         CommandParam(
    #             name="event_mode",
    #             description="Choose if events are managed for the whole server or in individual channels (default=Server-wide)",
    #             param_type=AppCommandOptionType.string,
    #             required=True,
    #             choices=EVENT_MODE_CHOICES
    #         )
    #     ]
    # }
}
