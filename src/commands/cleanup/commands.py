from mypy_boto3_dynamodb.service_resource import Table
from botocore.exceptions import ClientError

import utils.message_helper as msg_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def get_all_users