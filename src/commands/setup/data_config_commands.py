from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import constants
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def set_participant_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Sets the participant_role property of the existing SERVER/CHANNEL record.
    - Only allows users with 'Manage Server' permission.
    """
    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to change the organizer role."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    existing_item = db_helper.get_server_config(server_id, aws_services.dynamotb_table)
    if not existing_item:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set the organizer role there 👍"
        )

    participant_role = event.get_command_input_value("participant_role")
    should_remove_role = event.get_command_input_value("remove_role") or False # Default to No removal

    try:
        if should_remove_role:
            participant_role = "" # Set to empty string to remove
        aws_services.dynamotb_table.update_item(
            # Participant role is configured at level of event data, not server config
            Key={"PK": pk, "SK": constants.SK_SERVER},
            UpdateExpression=f"SET {event_data_keys.PARTICIPANT_ROLE} = :r",
            ExpressionAttributeValues={":r": participant_role}
        )
    except ClientError:
        raise

    operation = "removed" if should_remove_role else "updated"
    return ResponseMessage(
        content=f"👍 Participant role {operation} successfully."
    )
