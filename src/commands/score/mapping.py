from discord import AppCommandOptionType

import commands.score.score_constants as score_constants
import commands.score.score_commands as score_commands
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

_AMOUNT_PARAM = CommandParam(
    name="amount",
    description="How much to change your score by (default: 1)",
    param_type=AppCommandOptionType.integer,
    required=False,
    choices=None
)

_SCORE_PARAM = CommandParam(
    name="score",
    description="The exact score to set (0 or higher)",
    param_type=AppCommandOptionType.integer,
    required=True,
    choices=None
)

score_commands_mapping: CommandMapping = {
    "score-add": {
        "function": score_commands.score_add,
        "description": "Add to your score for an event (default: 1)",
        "params": [EVENT_NAME_PARAM, _AMOUNT_PARAM]
    },
    "score-deduct": {
        "function": score_commands.score_deduct,
        "description": "Subtract from your score for an event (default: 1)",
        "params": [EVENT_NAME_PARAM, _AMOUNT_PARAM]
    },
    "score-set": {
        "function": score_commands.score_set,
        "description": "Set your score for an event to an exact value",
        "params": [EVENT_NAME_PARAM, _SCORE_PARAM]
    },
    "score-view": {
        "function": score_commands.score_view,
        "description": "Show your score and rank for an event",
        "params": [EVENT_NAME_PARAM]
    },
    "scoreboard": {
        "function": score_commands.show_scoreboard,
        "description": "Show the scoreboard for an event, highest score first",
        "params": [EVENT_NAME_PARAM]
    },
    "scoreboard-toggle": {
        "function": score_commands.toggle_scoreboard,
        "description": "Open or close score reporting for an event (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="state",
                description="Set to 'Start' to accept score changes, and set to 'End' to reject them",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(name="Start", value=score_constants.START_PARAM),
                    ParamChoice(name="End", value=score_constants.END_PARAM)
                ]
            )
        ]
    },
    "scoreboard-reset": {
        "function": score_commands.reset_scoreboard,
        "description": "Clear every score for an event (Organizer only)",
        "params": [EVENT_NAME_PARAM]
    },
    "score-override": {
        "function": score_commands.score_override,
        "description": "Set a user's score for an event to an exact value (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="The user whose score to set",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            ),
            _SCORE_PARAM
        ]
    },
    "score-remove": {
        "function": score_commands.score_remove,
        "description": "Remove a user from an event's scoreboard (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="The user to remove from the scoreboard",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            )
        ]
    }
}
