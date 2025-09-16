from discord.app_commands import Parameter
from commands.types import CommandMapping
import retrieve_players.retrieve_players_main as retrieve_players_main

retrieve_commands: CommandMapping = {
    "retrieve_players": {
        "function": retrieve_players_main.retrieve_player_list,
        "description": "Retrieves list of players of an event",
        "params": [Parameter(
            name="retrieve_player_list", 
            description="Retrieve a list of players from a start.gg link",
            required=True)]
    }
}