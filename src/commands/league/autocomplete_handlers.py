from discord import AppCommandOptionType

from aws_services import AWSServices
from commands.models.autocomplete_response import AutocompleteResponse
from commands.models.command_param import CommandParam, ParamChoice
from commands.models.discord_event import DiscordEvent
import database.dynamodb_utils as db_helper


def autocomplete_league_name(event: DiscordEvent, aws_services: AWSServices) -> AutocompleteResponse:
    server_id = event.get_server_id()
    leagues = db_helper.get_leagues_for_server(server_id, aws_services.dynamodb_table)
    # name is the display label; value is the league_id for easy indexing
    choices = [ParamChoice(name=name, value=league_id) for name, league_id in leagues]
    return AutocompleteResponse(choices)


# Shared param used by any command that needs to target a specific league.
# The autocomplete value is the league_id, not the display name.
LEAGUE_NAME_PARAM = CommandParam(
    name="league_name",
    description="Name of the league",
    param_type=AppCommandOptionType.string,
    required=True,
    choices=None,
    autocomplete=True,
    autocomplete_handler=autocomplete_league_name
)
