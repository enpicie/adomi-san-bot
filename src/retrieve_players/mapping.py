from commands.types import CommandMapping
import retrieve_players.retrieve as retrieve

retrieve_commands: CommandMapping = {
    "retrieve_players": {
        "function": retrieve.retrieve_player_list,
        "description": "Retrieves list of players of an event",
        "params": ["startgg_link"]
    }
}