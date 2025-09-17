from discord import AppCommandOptionType
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import get_startgg_attendees.get_startgg_attendees_main as get_startgg_attendees_main

get_attendees_commands: CommandMapping = {
    "get_startgg_attendees": {
        "function": get_startgg_attendees_main.get_startgg_attendees_list,
        "description": "Retrieves list of players of an event",
        "params": [
            CommandParam(name = "bracket_link",
                         description = "Place a link for a start.gg bracket event",
                         type = AppCommandOptionType.string,
                         required= True
                         )
        ]
    }
}