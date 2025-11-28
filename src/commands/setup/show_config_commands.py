import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def show_event_roles(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    server_id = event.get_server_id()

    config_result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(config_result, ResponseMessage):
        return config_result

    event_data_result = db_helper.get_server_event_data_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(event_data_result, ResponseMessage):
        return event_data_result

    participant_role = (
        message_helper.get_role_ping(event_data_result.participant_role)
        if event_data_result.participant_role
        else "No Participant role set"
    )

    return ResponseMessage(
        content=f"**Event Roles:**\n"
                f"- Organizer: {message_helper.get_role_ping(config_result.organizer_role)}\n"
                f"- Participant: {participant_role}"
    ).with_silent_pings()
