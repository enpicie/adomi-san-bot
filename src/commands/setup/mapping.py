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
                name="event_mode",
                description="Mode for managing event data, determining if events are managed for the whole server or in individual channels (default is Server-wide).",
                param_type=AppCommandOptionType.string.value,
                required=False,
                choices=[
                    ParamChoice(name="Server-wide", value=EventMode.SERVER_WIDE.value),
                    ParamChoice(name="Per-channel", value=EventMode.PER_CHANNEL.value),
                ]
            )
        ]
    }
}
