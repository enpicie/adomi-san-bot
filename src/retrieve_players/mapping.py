#from discord.app_commands import Parameter
from commands.types import CommandMapping, Parameter
import retrieve_players.retrieve_players_main as retrieve_players_main

retrieve_commands: CommandMapping = {
    "retrieve_players": {
        "function": retrieve_players_main.retrieve_player_list,
        "description": "Retrieves list of players of an event",
        "params": [Parameter(name="Startgg_link", description="Place a link for a start.gg event", required=True)]
    }
}