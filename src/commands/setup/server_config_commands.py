from mypy_boto3_dynamodb.service_resource import Table

import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.server_config import ServerConfig

def setup_server(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets up a CONFIG record for a server in DynamoDB if it does not already exist."""
    table: Table = aws_services.dynamodb_table
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
        return error_message

    server_id = event.get_server_id()

    # Check if config already exists
    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if not isinstance(result, ResponseMessage):
        return ResponseMessage(
            content=f"This server is already set up! Check out other commands to configure the settings for this server."
        )

    organizer_role = event.get_command_input_value("organizer_role")
    print(f"Organizer role: {organizer_role}")

    pk = db_helper.build_server_pk(server_id)

    table.put_item(
        Item={
            "PK": pk,
            "SK": ServerConfig.Keys.SK_CONFIG,
            ServerConfig.Keys.SERVER_ID: server_id,
            ServerConfig.Keys.ORGANIZER_ROLE: organizer_role
        }
    )

    return ResponseMessage(
        content="👍 Server setup complete."
    )

def set_organizer_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the organizer_role property of the existing CONFIG record."""
    table: Table = aws_services.dynamodb_table
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
         return error_message

    server_id = event.get_server_id()
    pk = db_helper.build_server_pk(server_id)

    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(result, ResponseMessage):
        return result

    organizer_role = event.get_command_input_value("organizer_role")

    table.update_item(
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        UpdateExpression=f"SET {ServerConfig.Keys.ORGANIZER_ROLE} = :r",
        ExpressionAttributeValues={":r": organizer_role}
    )

    return ResponseMessage(
        content=f"👍 Organizer role updated successfully."
    )

def set_participant_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the participant_role property of the existing SERVER/CHANNEL event data record."""
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
          return error_message

    server_id = event.get_server_id()

    # Verify that the server configuration exists before proceeding.
    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(result, ResponseMessage):
        # The original code used get_server_config_or_fail, which usually returns the
        # config or an error message if the config is not found.
        return result

    event_id = event.get_command_input_value("event_name")
    participant_role = event.get_command_input_value("participant_role")
    should_remove_role = event.get_command_input_value("remove_role") or False # Default to No removal

    # Determine the final value for the participant role
    if should_remove_role:
        participant_role = "" # Set to empty string to remove

    aws_services.dynamodb_table.update_item(
        Key={"PK": db_helper.build_server_pk(server_id), "SK": EventData.Keys.SK_EVENT_PREFIX + event_id},
        UpdateExpression=f"SET {EventData.Keys.PARTICIPANT_ROLE} = :r",
        ExpressionAttributeValues={":r": participant_role}
    )

    operation = "removed" if should_remove_role else "updated"
    return ResponseMessage(
        content=f"👍 Participant role {operation} successfully."
    )
