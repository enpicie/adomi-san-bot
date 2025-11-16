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
    Sets 'event_mode' and 'organizer_role' based on command inputs.
    Only allows users with 'Manage Server' permission to run this command.
    Default event_mode is 'server-wide'.
    'organizer_role' is required and designates role allowed to use privileged bot commands.
    EVENT_MODE FUNCCTIONALITY IS CURRENTLY DISABLED. Planned for later phase. Only using SERVER_WIDE.
    """
    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to set things up for this server."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    try:
        existing_item = db_helper.get_server_config(server_id, table)
        if existing_item:
            return ResponseMessage(
                content=f"This server is already set up! Check out other commands to configure the settings for this server."
            )

        # TODO: set based on user-input when functionality is fully built.
        event_mode = EventMode.SERVER_WIDE.value
        print(f"Event mode: {event_mode}")
        organizer_role = event.get_command_input_value("organizer_role")
        print(f"Organizer role: {organizer_role}")

        table.put_item(
            Item={
                "PK": pk,
                "SK": SK_CONFIG,
                "event_mode": EventMode.SERVER_WIDE.value
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

def set_organizer_role(event: DiscordEvent, table: Table) -> ResponseMessage:
    """
    Sets the organizer_role property of the existing CONFIG record.
    - Only allows users with 'Manage Server' permission.
    """

    user_permissions = event.get_user_permission_int()
    if not permissions_helper.has_manage_server_permission(user_permissions):
        return ResponseMessage(
            content="⚠️ You need the 'Manage Server' permission to change the organizer role."
        )

    server_id = event.get_server_id()
    pk = db_helper.get_server_pk(server_id)

    existing_item = db_helper.get_server_config(server_id, table)
    if not existing_item:
        return ResponseMessage(
            content="This server is not set up! Run `/setup-server` first to get started. "
                    "You can set the organizer role there 👍"
        )

    organizer_role = event.get_command_input_value("organizer_role")

    try:
        table.update_item(
            Key={"PK": pk, "SK": SK_CONFIG},
            UpdateExpression="SET organizer_role = :r",
            ExpressionAttributeValues={":r": organizer_role}
        )
    except ClientError:
        raise

    return ResponseMessage(
        content=f"👍 Organizer role updated successfully."
    )
