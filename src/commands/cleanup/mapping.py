from commands.models.command_mapping import CommandMapping
from discord import AppCommandOptionType
import commands.check_in.commands as commands

checkin_commands: CommandMapping = {
    "get-all-users": {
        "function": commands.get_all_users,
        "description": "Retrieve all users in CONFIG table",
        "params": []
    },
    "search-user": {
        "function": commands.search_user,
        "description": "Search user given string argument",
        "params": [
            {
                "name": "searchstring",
                "description": "Search string for DB query",
                "type": AppCommandOptionType.string
            }
        ]
    },
    "delete-user": {
        "function": commands.delete_user,
        "description": "Delete given user from CONFIG",
        "params": [
            {
                "name": "user",
                "description": "Discord user passed as argument",
                "type": AppCommandOptionType.user
            }
        ]
    },
    "delete-channel": {
        "function": commands.delete_channel,
        "description": "Delete given Discord channel",
        "params": [
            {
                "name": "channel",
                "description": "Discord channel passed as argument",
                "type": AppCommandOptionType.channel
            }
        ]
    },
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
