import database.dynamodb_utils as db_helper
from aws_services import AWSServices
from commands.models.autocomplete_response import AutocompleteResponse
from commands.models.command_param import ParamChoice
from commands.models.discord_event import DiscordEvent


def autocomplete_plan_name(event: DiscordEvent, aws_services: AWSServices) -> AutocompleteResponse:
    """Returns the server's planned schedule events as choices (name and value: plan name)."""
    server_id = event.get_server_id()
    plans = db_helper.get_schedule_plans_for_server(server_id, aws_services.dynamodb_table)
    choices = [ParamChoice(name=p.plan_name, value=p.plan_name) for p in plans]
    # Discord rejects autocomplete payloads with more than 25 choices
    return AutocompleteResponse(choices[:25])
