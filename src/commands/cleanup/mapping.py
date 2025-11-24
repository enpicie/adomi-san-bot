from commands.models.command_mapping import CommandMapping
from discord import AppCommandOptionType
import commands.cleanup.commands as commands

cleanup_commands: CommandMapping = {
    "delete-server": {
        "function": commands.delete_server,
        "description": "Delete server by ID",
        "params": [
            {
                "name": "server",
                "description": "Discord server passed as argument",
                "type": AppCommandOptionType.string
            }
        ]
    }
}
