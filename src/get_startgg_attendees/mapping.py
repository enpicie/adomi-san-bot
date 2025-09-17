from discord import app_commands
from commands.types import CommandMapping
import get_startgg_attendees.get_startgg_attendees_main as get_startgg_attendees_main

# Source: https://stackoverflow.com/questions/1528932/how-to-create-inline-objects-with-properties

get_attendees_commands: CommandMapping = {
    "retrieve_players": {
        "function": get_startgg_attendees_main.get_startgg_attendees_list,
        "description": "Retrieves list of players of an event",
        "params": [
            {
                "name": "startgg_bracket_link",
                "description": "Place a link for a start.gg bracket event",
                "type": str,
                "required": True
            }
        ]
    }
}