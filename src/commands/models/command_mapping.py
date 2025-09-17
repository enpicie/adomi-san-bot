from typing import Callable, List, TypedDict

from discord import Message
from commands.models.command_param import CommandParam

class CommandEntry(TypedDict):
    function: Callable[[dict], Message]
    description: str
    params: List[CommandParam]

CommandMapping = dict[str, CommandEntry]
