from typing import Callable, List, TypedDict

from discord import Message
from discord.app_commands import Parameter

class CommandEntry(TypedDict):
    function: Callable[[dict], Message]
    description: str
    params: List[Parameter]

CommandMapping = dict[str, CommandEntry]
