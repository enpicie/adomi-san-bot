from discord.app_commands import Parameter
from commands.types import CommandMapping
import get_startgg_attendees.get_startgg_attendees_main as get_startgg_attendees_main

get_attendees_commands: CommandMapping = {
    "retrieve_players": {
        "function": get_startgg_attendees_main.get_startgg_attendees_list,
        "description": "Retrieves list of players of an event",
        "params": [
            {
                "name": "bracket_link",
                "description": "Place a link for a start.gg bracket event",
                "required": True
            }
        ]
    }
}