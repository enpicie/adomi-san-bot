from mypy_boto3_dynamodb.service_resource import Table

import database.dynamodb_utils as db_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as message_helper
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
    notification_channel = event.get_command_input_value("notification_channel")
    ping_organizers = event.get_command_input_value("ping_organizers") or False

    pk = db_helper.build_server_pk(server_id)

    server_name = discord_helper.get_guild_name(server_id)
    print(f"[setup] Fetched server name: {server_name!r} for server_id={server_id!r}")

    table.put_item(
        Item={
            "PK": pk,
            "SK": ServerConfig.Keys.SK_CONFIG,
            ServerConfig.Keys.SERVER_ID: server_id,
            ServerConfig.Keys.SERVER_NAME: server_name,
            ServerConfig.Keys.ORGANIZER_ROLE: organizer_role,
            ServerConfig.Keys.NOTIFICATION_CHANNEL_ID: notification_channel,
            ServerConfig.Keys.PING_ORGANIZERS: ping_organizers,
        }
    )

    return ResponseMessage(
        content=(
            "👍 Server setup complete"
            f"with organizer role {message_helper.get_role_ping(organizer_role)}"
            f" and notifications sent to {message_helper.get_channel_mention(notification_channel)}."
            " Please ensure I have access to the notificaton channel and high role priority."
        )
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
        content=f"👍 Notification channel updated successfully. Please ensure I have access to this channel. {ping_note}"
    )


def setup_event_reminders(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """Configures the announcement channel, optional role, and default reminder behavior for events."""
    error_message = permissions_helper.require_manage_server_permission(event)
    if isinstance(error_message, ResponseMessage):
        return error_message

    server_id = event.get_server_id()
    pk = db_helper.build_server_pk(server_id)

    result = db_helper.get_server_config_or_fail(server_id, aws_services.dynamodb_table)
    if isinstance(result, ResponseMessage):
        return result

    announcement_channel = event.get_command_input_value("announcement_channel")
    announcement_role = event.get_command_input_value("announcement_role")
    remind_by_default = event.get_command_input_value("remind_by_default")

    update_expr = f"SET {ServerConfig.Keys.ANNOUNCEMENT_CHANNEL_ID} = :channel"
    expression_values = {":channel": announcement_channel}

    if announcement_role is not None:
        update_expr += f", {ServerConfig.Keys.ANNOUNCEMENT_ROLE_ID} = :role"
        expression_values[":role"] = announcement_role

    if remind_by_default is not None:
        update_expr += f", {ServerConfig.Keys.SHOULD_ALWAYS_REMIND} = :remind"
        expression_values[":remind"] = remind_by_default

    aws_services.dynamodb_table.update_item(
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expression_values
    )

    role_note = f" Reminders will ping {message_helper.get_role_ping(announcement_role)}." if announcement_role else ""
    remind_note = " Events will have reminders on by default." if remind_by_default else ""
    return ResponseMessage(
        content=(
            f"👍 Event reminders configured. Announcements will be posted to "
            f"{message_helper.get_channel_mention(announcement_channel)}.{role_note}{remind_note}"
            " Please ensure I have access to the announcement channel."
        )
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
