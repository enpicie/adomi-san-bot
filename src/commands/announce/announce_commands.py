from botocore.exceptions import ClientError

import constants
import database.dynamodb_queries as db_helper
import utils.message_helper as msg_helper
from aws_services import AWSServices
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage
from database.event_data_keys import START_MESSAGE, END_MESSAGE

def announce_event(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Sends the event start announcement for the current event.
    """
    attr_get = ""

    pk = db_helper.get_server_pk(event.get_server_id())
    sk = constants.SK_SERVER

    announce_type = event.get_command_input_value("announce_type")
    
    if announce_type == "start":
        attr_get = START_MESSAGE
    else:
        attr_get = END_MESSAGE
    
    response = aws_services.dynamotb_table.get_item(
        Key={"PK": pk, "SK": sk},
        ProjectionExpression=attr_get
    )

    announce_response = next(iter(response["item"]))

    return ResponseMessage(
        content=announce_response
    )

def set_event_message(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    """
    Update server record and set the event start message to be used for announcements.
    """
    attr_set = ""

    pk = db_helper.get_server_pk(event.get_server_id())
    sk = constants.SK_SERVER
    
    announcement = event.get_command_input_value("announcement")
    announce_type = event.get_command_input_value("announce_type")

    if announce_type == "start":
        attr_set = START_MESSAGE
    else:
        attr_set = END_MESSAGE

    aws_services.dynamotb_table.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET :attr_set.message = :announcement",
        ExpressionAttributeNames={":attr_set": attr_set},
        ExpressionAttributeNames={":announcement": announcement}
    )
    return ResponseMessage(
        content=f"✅ Set the {announce_type} announcement for the current event!"
    )

