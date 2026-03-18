from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM
import commands.startgg.startgg_commands as startgg_commands

startgg_commands_mapping: CommandMapping = {
    "startgg-report-score": {
        "function": startgg_commands.report_score,
        "description": "Report the result of a start.gg bracket set",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="winner",
                description="Player who won the set",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            ),
            CommandParam(
                name="loser",
                description="Player who lost the set",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            ),
            CommandParam(
                name="score",
                description="Score in '<winner games>-<loser games>' format, e.g. '2-1' (winner score first)",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            )
        ]
    }
}
