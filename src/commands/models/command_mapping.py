from typing import Callable, List, TypedDict
from mypy_boto3_dynamodb.service_resource import Table

from commands.models.command_param import CommandParam
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

class CommandEntry(TypedDict):
    function: Callable[[DiscordEvent, Table], ResponseMessage]
    description: str
    params: List[CommandParam]

CommandMapping = dict[str, CommandEntry]
