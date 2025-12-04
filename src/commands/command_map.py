from commands.models.command_mapping import CommandMapping

from commands.help.mapping import help_commands
from commands.check_in.mapping import checkin_commands
from commands.setup.mapping import setup_commands
from commands.announce.mapping import announce_commands
from commands.get_registered.mapping import get_registered_commands

command_map: CommandMapping = {
} | (
    help_commands |
    checkin_commands |
    setup_commands | 
    announce_commands |
    setup_commands |
    setup_commands |
    get_registered_commands
)
