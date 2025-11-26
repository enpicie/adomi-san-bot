from discord import AppCommandOptionType

import commands.get_registered.registered_commands as registered_commands
import commands.get_registered.startgg.startgg_commands as startgg_commands
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam

get_registered_commands: CommandMapping = {
    "show-registered": {
        "function": registered_commands.show_registered,
        "description": "Show list of registered users",
        "params": []
    },
    "clear-registered": {
        "function": registered_commands.clear_registered,
        "description": "Clear list of registered users",
        "params": []
    },
    "get-registered-startgg": {
        "function": startgg_commands.get_registered_startgg,
        "description": "Gets registered participants from a start.gg Tournement Event, replacing existing registered list",
        "params": [
            CommandParam(
                name = "event_link",
                description = "Link to a start.gg Tournament Event (ex: start.gg/tournament/midweek-melting/event/mbaacc-bracket)",
                param_type = AppCommandOptionType.string,
                required= True,
                choices = None
            )
        ]
    }
}
