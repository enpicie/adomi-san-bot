from botocore.exceptions import ClientError

import constants
import database.dynamodb_queries as db_helper
import database.event_data_keys as event_data_keys
import database.config_data_helper as config_helper
import utils.discord_api_helper as discord_helper
import utils.message_helper as msg_helper
from aws_services import AWSServices
from database.models.participant import Participant
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def get_participants_startgg(event: DiscordEvent, aws_services: AWSServices) -> ResponseMessage:
    # Implementation of the function to get participants from start.gg

    pass
