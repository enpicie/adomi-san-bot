from typing import Callable, List, TypedDict

from commands.models.response_message import ResponseMessage
from commands.models.command_param import CommandParam

class CommandEntry(TypedDict):
    function: Callable[[dict], ResponseMessage]
    description: str
    params: List[CommandParam]

CommandMapping = dict[str, CommandEntry]
