import database.dynamodb_utils as db_helper
import utils.adomin_messages as adomin_messages
import utils.message_helper as message_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData
from database.models.server_config import ServerConfig

# Planned future feature: event start/end announcements.
# This package is intentionally NOT registered in command_map.py — these commands
# are not exposed to Discord until the feature is completed.

def announce_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Sends the event start announcement for the current event.
    """
    announce_type = event.get_command_input_value("announce_type")
    ping_participants = event.get_command_input_value("ping_participants")

    message_key = EventData.Keys.START_MESSAGE if announce_type == "start" else EventData.Keys.END_MESSAGE

    pk = db_helper.build_server_pk(event.get_server_id())

    db_response = aws_services.dynamodb_table.get_item(
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        ProjectionExpression=f"{message_key}, {EventData.Keys.PARTICIPANT_ROLE}"
    )
    existing_data = db_response.get("Item")
    if not existing_data:
        return ResponseMessage(content=adomin_messages.SERVER_EVENT_DATA_MISSING)

    event_data = EventData.from_dynamodb(existing_data)

    role_ping = message_helper.get_role_ping(event_data.participant_role) + "\n" if ping_participants else ""

    response_message = event_data.start_message if announce_type == "start" else event_data.end_message

    return ResponseMessage(
        content= role_ping + response_message
    )

def set_event_message(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Update server record and set the event start message to be used for announcements.
    """

    message_text = event.get_command_input_value("message_text")
    announce_type = event.get_command_input_value("announce_type")

    message_key = EventData.Keys.START_MESSAGE if announce_type == "start" else EventData.Keys.END_MESSAGE

    pk = db_helper.build_server_pk(event.get_server_id())

    aws_services.dynamodb_table.update_item(
        # Announcements configured at level of event data, not server config
        Key={"PK": pk, "SK": ServerConfig.Keys.SK_CONFIG},
        UpdateExpression=f"SET {message_key} = :msg",
        ExpressionAttributeValues={":msg": message_text}
    )
    return ResponseMessage(
        content=f"✅ Set the {announce_type} announcement for the current event!"
    )
