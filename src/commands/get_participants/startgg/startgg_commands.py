from botocore.exceptions import ClientError

import constants
import database.dynamodb_utils as db_helper
from database.models.event_data import EventData
import database.dynamodb_utils as config_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as msg_helper
import commands.get_participants.startgg.startgg_api as startgg_api
from aws_services import AWSServices
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def get_participants_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    table = aws_services.dynamodb_table
    server_id = event.get_server_id()
    pk = db_helper.build_server_pk(server_id)
    sk = constants.SK_SERVER

    organizer_role = config_helper.try_get_organizer_role(server_id, table)
    if isinstance(organizer_role, ResponseMessage):
        return organizer_role # Directly return the error message

    if organizer_role not in event.get_user_roles():
        return ResponseMessage(
            content="❌ You don't have permission to clear check-ins. "
                    "Only users with the server's designated organizer role can do this."
        )

    startgg_event = startgg_api.query_startgg_event(event.get_command_input_value("event_link"))

    pass
