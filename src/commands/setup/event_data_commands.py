from botocore.exceptions import ClientError

import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData

def set_participant_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the participant_role property of the existing SERVER/CHANNEL event data record."""
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
          return error_message

    server_id = event.get_server_id()

    config_result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(config_result, ResponseMessage):
        return config_result

    participant_role = event.get_command_input_value("participant_role")
    should_remove_role = event.get_command_input_value("remove_role") or False # Default to No removal

    try:
        if should_remove_role:
            participant_role = "" # Set to empty string to remove

        aws_services.dynamodb_table.update_item(
            # Participant role is configured at level of event data (SK_SERVER for server-wide mode)
            Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_SERVER},
            UpdateExpression=f"SET {EventData.Keys.PARTICIPANT_ROLE} = :r",
            ExpressionAttributeValues={":r": participant_role}
        )
    except ClientError:
        raise

    operation = "removed" if should_remove_role else "updated"
    return ResponseMessage(
        content=f"👍 Participant role {operation} successfully."
    )
