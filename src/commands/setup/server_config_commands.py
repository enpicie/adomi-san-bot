from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import database.dynamodb_utils as db_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from enums import EventMode
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

    try:
        # Check if config already exists
        result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
        if not isinstance(result, ResponseMessage):
            return ResponseMessage(
                content=f"This server is already set up! Check out other commands to configure the settings for this server."
            )

        # TODO: set based on user-input when functionality is fully built.
        event_mode = EventMode.SERVER_WIDE.value
        print(f"Event mode: {event_mode}")
        organizer_role = event.get_command_input_value("organizer_role")
        print(f"Organizer role: {organizer_role}")


        pk = db_helper.build_server_pk(server_id)

        # 1. Create Server Config Record (SK_CONFIG)
        table.put_item(
            Item={
                "PK": pk,
                "SK": ServerConfig.Keys.SK_CONFIG,
                ServerConfig.Keys.EVENT_MODE: EventMode.SERVER_WIDE.value,
                ServerConfig.Keys.ORGANIZER_ROLE: organizer_role
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
        )

        # 2. Create Event Data Record (SK_SERVER) for server-wide mode
        if event_mode == EventMode.SERVER_WIDE.value:
            table.put_item(
                Item={
                    "PK": pk,
                    "SK": EventData.Keys.SK_SERVER,
                    EventData.Keys.CHECKED_IN: {}, # Initialize empty checked_in map
                    EventData.Keys.REGISTERED: {}, # Initialize empty registered map
                    EventData.Keys.QUEUE: {}     # Initialize empty queue map
                },
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )
        # TODO: implement case for Per-Channel when modes are implemented

        return ResponseMessage(
            content=f"👍 Server setup complete with event mode `{event_mode}`."
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return ResponseMessage(
                content=f"Server `{server_id}` already has `{ServerConfig.Keys.SK_CONFIG}` record."
            )
        raise

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

    try:
        table.update_item(
            Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
            UpdateExpression=f"SET {ServerConfig.Keys.ORGANIZER_ROLE} = :r",
            ExpressionAttributeValues={":r": organizer_role}
        )
    except ClientError:
        raise

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

    participant_role = event.get_command_input_value("participant_role")
    should_remove_role = event.get_command_input_value("remove_role") or False # Default to No removal

    try:
        # Determine the final value for the participant role
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
