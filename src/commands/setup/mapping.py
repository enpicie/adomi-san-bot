from discord import AppCommandOptionType

from enums import EventMode
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.setup.server_commands as server_commands

EVENT_MODE_CHOICES = [
    ParamChoice(name="Server-wide", value=EventMode.SERVER_WIDE.value),
    ParamChoice(name="Per-channel", value=EventMode.PER_CHANNEL.value)
]

setup_commands: CommandMapping = {
    "setup-server": {
        "function": server_commands.setup_server,
        "description": "Set up this server for use with the bot.",
        "params": [
            CommandParam(
                name="event_mode",
                description="Choose if events are managed for the whole server or in individual channels (default=Server-wide)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=EVENT_MODE_CHOICES
            )
        ]
    },
    "setup-event-mode": {
        "function": server_commands.setup_event_mode,
        "description": "Set event-mode for how bot will manage event data.",
        "params": [
            CommandParam(
                name="event_mode",
                description="Choose if events are managed for the whole server or in individual channels (default=Server-wide)",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=EVENT_MODE_CHOICES
            )
        ]
    }
}
