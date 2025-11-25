from discord import AppCommandOptionType

import commands.get_participants.startgg.startgg_commands as startgg_commands
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam

get_participants_commands: CommandMapping = {
    "get-participants-startgg": {
        "function": startgg_commands.get_participants_startgg,
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
