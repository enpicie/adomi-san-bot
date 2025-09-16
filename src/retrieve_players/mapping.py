from commands.types import CommandMapping
from retrieve_players.retrieve_action import retrieve_player_list

retrieve_commands: CommandMapping = {
    "retrieve_players": {
        "function": retrieve_player_list,
        "description": "Retrieves list of players of an event",
        "params": ["startgg_link"]
    }
}