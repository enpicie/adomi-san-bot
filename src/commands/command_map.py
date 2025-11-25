from commands.models.command_mapping import CommandMapping

from commands.check_in.mapping import checkin_commands
from commands.setup.mapping import setup_commands
from commands.get_registered.mapping import get_registered_commands

command_map: CommandMapping = {
} | (
    checkin_commands |
    setup_commands |
    get_registered_commands
)
