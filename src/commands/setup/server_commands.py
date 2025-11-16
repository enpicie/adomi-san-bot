from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import constants
import utils.dynamodb_helper as db_helper
import utils.permissions_helper as permissions_helper
from enums import EventMode
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

SK_CONFIG = "CONFIG"
SK_SERVER = "SERVER"

def setup_server(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Sets up a CONFIG record for a server in DynamoDB if it does not already exist.
    Adds an 'event_mode' attribute based on a command parameter in the event.
    Only allows users with 'Manage Server' permission to run this command.
    Default event_mode is 'server-wide'.
    If 'event_mode' is 'server-wide', also creates a SERVER record.
    """
    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to set things up for this server."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    try:
        # Check if the CONFIG record already exists
        existing_item = db_helper.get_server_config(server_id, table)
        if existing_item:
            return ResponseMessage(
                content=f"This server is already set up! Check out other commands to configure the settings for this server."
            )

        event_mode = event.get_command_input_value("event_mode")

        # Create CONFIG record
        table.put_item(
            Item={
                "PK": pk,
                "SK": SK_CONFIG,
                "event_mode": event_mode or EventMode.SERVER_WIDE.value
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
        )

        # If event_mode is 'server-wide' (default), create a SERVER record
        if not event_mode or event_mode == EventMode.SERVER_WIDE.value:
            table.put_item(
                Item={
                    "PK": pk,
                    "SK": SK_SERVER,
                    "checked_in": {}, # Initialize empty checked_in map
                    "queued": {}     # Initialize empty queued map
                },
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
            )

        return ResponseMessage(
            content=f"👍 Server setup complete with event mode `{event_mode or EventMode.SERVER_WIDE.value}`."
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return ResponseMessage(
                content=f"Server `{server_id}` already has `{constants.SK_CONFIG}` record."
            )
        raise

def setup_event_mode(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Updates the event_mode property of the existing CONFIG record.
    Only allows users with 'Manage Server' permission.
    """
    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to change the event mode."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    # Check CONFIG exists
    existing_item = db_helper.get_server_config(server_id, table)
    if not existing_item:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set event-mode there 👍"
        )

    event_mode = event.get_command_input_value("event_mode")

    try:
        # Update the existing CONFIG record
        table.update_item(
            Key={"PK": pk, "SK": SK_CONFIG},
            UpdateExpression="SET event_mode = :m",
            ExpressionAttributeValues={":m": event_mode}
        )

        return ResponseMessage(
            content=f"👍 Changed event mode to `{event_mode}`."
        )

    except ClientError as e:
        raise

