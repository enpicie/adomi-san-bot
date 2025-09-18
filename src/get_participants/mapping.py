from discord import AppCommandOptionType
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import get_participants.startgg.get_startgg_participants_main as get_startgg_participants_main


get_participants_commands: CommandMapping = {
    "get_startgg_participants": {
        "function": get_startgg_participants_main.get_startgg_participants_list,
        "description": "Retrieves list of participants of an event",
        "params": [
            CommandParam(name = "bracket_link",
                         description = "Place a link for a start.gg bracket event",
                         param_type = AppCommandOptionType.string,
                         required= True,
                         choices = None
                         )
        ]
    }
}