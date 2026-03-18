from discord import AppCommandOptionType

from aws_services import AWSServices
from commands.models.autocomplete_response import AutocompleteResponse
from commands.models.command_param import CommandParam, ParamChoice
from commands.models.discord_event import DiscordEvent
from commands.event.timezone_helper import TIMEZONE_OPTIONS
import database.dynamodb_utils as db_helper


def autocomplete_event_timezone(_event: DiscordEvent, _aws_services: AWSServices) -> AutocompleteResponse:
    return AutocompleteResponse([tz.to_param_choice() for tz in TIMEZONE_OPTIONS])


def autocomplete_event_name(event: DiscordEvent, aws_services: AWSServices) -> AutocompleteResponse:
    server_id = event.get_server_id()
    events = db_helper.get_events_for_server(server_id, aws_services.dynamodb_table)
    # name is the display label; value is the event_id for easy indexing
    choices = [ParamChoice(name=name, value=event_id) for name, event_id in events]
    return AutocompleteResponse(choices)


# Shared param used by any command that needs to target a specific event.
# The autocomplete value is the event_id, not the display name.
EVENT_NAME_PARAM = CommandParam(
    name="event_name",
    description="Name of the event",
    param_type=AppCommandOptionType.string,
    required=True,
    choices=None,
    autocomplete=True,
    autocomplete_handler=autocomplete_event_name
)
