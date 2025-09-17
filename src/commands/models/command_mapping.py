from dataclasses import dataclass
from typing import Callable, List

from discord import Message
from commands.models.command_param import CommandParam

@dataclass
class CommandEntry():
    function: Callable[[dict], Message]
    description: str
    params: List[CommandParam]

CommandMapping = dict[str, CommandEntry]
