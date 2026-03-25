from mypy_boto3_dynamodb.service_resource import Table

import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
import utils.permissions_helper as permissions_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
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

    server_name = discord_helper.get_guild_name(server_id)
    print(f"[setup] Fetched server name: {server_name!r} for server_id={server_id!r}")

    table.put_item(
        Item={
            "PK": pk,
            "SK": ServerConfig.Keys.SK_CONFIG,
            ServerConfig.Keys.SERVER_ID: server_id,
            ServerConfig.Keys.SERVER_NAME: server_name,
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

def setup_notifications(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the channel and ping preference for bot notifications."""
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
        return error_message

    server_id = event.get_server_id()
    pk = db_helper.build_server_pk(server_id)

    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(result, ResponseMessage):
        return result

    channel_id = event.get_command_input_value("channel")
    ping_organizers = event.get_command_input_value("ping_organizers") or False

    aws_services.dynamodb_table.update_item(
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        UpdateExpression=f"SET {ServerConfig.Keys.NOTIFICATION_CHANNEL_ID} = :c, {ServerConfig.Keys.PING_ORGANIZERS} = :p",
        ExpressionAttributeValues={":c": channel_id, ":p": ping_organizers}
    )

    ping_note = " Organizers will be pinged with notifications." if ping_organizers else ""
    return ResponseMessage(
        content=f"👍 Notification channel updated successfully.{ping_note}"
    )


def set_default_participant_role(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Sets the default_participant_role property of the server CONFIG record."""
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
        return error_message

    server_id = event.get_server_id()
    pk = db_helper.build_server_pk(server_id)

    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(result, ResponseMessage):
        return result

    participant_role = event.get_command_input_value("participant_role")

    aws_services.dynamodb_table.update_item(
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        UpdateExpression=f"SET {ServerConfig.Keys.DEFAULT_PARTICIPANT_ROLE} = :r",
        ExpressionAttributeValues={":r": participant_role}
    )

    return ResponseMessage(
        content=f"👍 Default participant role updated successfully."
    )
