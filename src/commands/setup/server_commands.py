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

def create_server_record(table: Table, pk: str) -> None:
    """Creates a SERVER record for the given PK in the provided DynamoDB table."""
    table.put_item(
        Item={
            "PK": pk,
            "SK": SK_SERVER,
            "checked_in": {}, # Initialize empty checked_in map
            "queued": {}     # Initialize empty queued map
        },
        ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
    )

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

        event_mode = event.get_command_input_value("event_mode") or EventMode.SERVER_WIDE.value

        # Create CONFIG record
        table.put_item(
            Item={
                "PK": pk,
                "SK": SK_CONFIG,
                "event_mode": event_mode or EventMode.SERVER_WIDE.value
            },
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)"
        )

        if event_mode == EventMode.SERVER_WIDE.value:
            create_server_record(table, pk)

        return ResponseMessage(
            content=f"👍 Server setup complete with event mode `{event_mode}`."
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
    - Only allows users with 'Manage Server' permission.
    - Returns a message if the event_mode is unchanged.
    - When switching to PER_CHANNEL:
        • Delete all SERVER records.
    - When switching to SERVER_WIDE:
        • Delete all CHANNEL* records.
        • Create a SERVER record.
    """

    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to change the event mode."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    # Load existing config
    existing_item = db_helper.get_server_config(server_id, table)
    if not existing_item:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set event-mode there 👍"
        )

    old_mode = existing_item.get("event_mode")
    new_mode = event.get_command_input_value("event_mode")

    # If no change, return early
    if new_mode == old_mode:
        return ResponseMessage(
            content=f"ℹ️ Event mode is already `{new_mode}`. My work is already complete 🫡!"
        )

    try:
        table.update_item(
            Key={"PK": pk, "SK": SK_CONFIG},
            UpdateExpression="SET event_mode = :m",
            ExpressionAttributeValues={":m": new_mode}
        )
    except ClientError:
        raise

    # Clean up old data based on new mode
    if new_mode == EventMode.PER_CHANNEL.value:
        # Delete old SERVER record
        server_items = db_helper.query_items_by_sk(server_id, table, SK_SERVER)
        for item in server_items:
            table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    elif new_mode == EventMode.SERVER_WIDE.value:
        # Delete old CHANNEL data
        channel_items = db_helper.query_items_with_sk_prefix(server_id, table, "CHANNEL")
        for item in channel_items:
            table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

        create_server_record(table, pk)

    old_data_note = "Server" if old_mode == EventMode.SERVER_WIDE.value else "Channel"

    return ResponseMessage(
        content=f"👍 Changed event mode from `{old_mode}` to `{new_mode}`."
                f" I've cleaned out old {old_data_note} data 🫡"
    )

