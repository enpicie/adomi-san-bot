from discord.app_commands import Parameter
from commands.types import CommandMapping
import get_startgg_attendees.get_startgg_attendees_main as get_startgg_attendees_main

get_attendees_commands: CommandMapping = {
    "retrieve_players": {
        "function": get_startgg_attendees_main.retrieve_player_list,
        "description": "Retrieves list of players of an event",
        "params": []
    }
}