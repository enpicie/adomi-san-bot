import constants
import database.dynamodb_utils as db_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def announce_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Sends the event start announcement for the current event.
    """
    announce_type = event.get_command_input_value("announce_type")

    message_key = EventData.Keys.START_MESSAGE if announce_type == "start" else EventData.Keys.END_MESSAGE

    pk = db_helper.build_server_pk(event.get_server_id())

    response = aws_services.dynamotb_table.get_item(
        Key={"PK": pk, "SK": EventData.Keys.SK_SERVER},
        ProjectionExpression=message_key
    )

    response_obj = EventData.from_dynamodb(response)

    response_message = response_obj.start_message if announce_type == "start" else response_obj.end_message

    return ResponseMessage(
        content=response_message
    )

def set_event_message(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Update server record and set the event start message to be used for announcements.
    """

    message_text = event.get_command_input_value("message_text")
    announce_type = event.get_command_input_value("announce_type")

    message_key = EventData.Keys.START_MESSAGE if announce_type == "start" else EventData.Keys.END_MESSAGE
    
    pk = db_helper.get_server_pk(event.get_server_id())

    aws_services.dynamotb_table.update_item(
        # Announcements configured at level of event data, not server config
        Key={"PK": pk, "SK": constants.SK_SERVER},
        UpdateExpression=f"SET {message_key} = :msg",
        ExpressionAttributeValues={":msg": message_text}
    )
    return ResponseMessage(
        content=f"✅ Set the {announce_type} announcement for the current event!"
    )
