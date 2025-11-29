import constants
import database.dynamodb_utils as db_helper
import utils.message_helper as message_helper
from aws_services import AWSServices
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.models.event_data import EventData


def announce_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Sends the event start announcement for the current event.
    """
    announce_type = event.get_command_input_value("announce_type")
    ping_participants = event.get_command_input_value("ping_participants")

    message_key = EventData.Keys.START_MESSAGE if announce_type == "start" else EventData.Keys.END_MESSAGE

    pk = db_helper.build_server_pk(event.get_server_id())

    response = aws_services.dynamotb_table.get_item(
        Key={"PK": pk, "SK": EventData.Keys.SK_SERVER},
        ProjectionExpression=f"{message_key}, {EventData.Keys.PARTICIPANT_ROLE}"
    )

    response_obj = EventData.from_dynamodb(response)

    # If ping_participants flag is set, build the announcement message starting with the role ping
    role_ping = message_helper.get_role_ping(response_obj.participant_role) + "\n" if ping_participants else ""

    # Select event start or end message depending on value of announce_type param
    response_message = response_obj.start_message if announce_type == "start" else response_obj.end_message

    # Concatenate the role ping and announcement message and return as response
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
