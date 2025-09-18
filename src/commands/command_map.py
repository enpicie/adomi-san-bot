from commands.models.command_mapping import CommandMapping

from check_in.mapping import checkin_commands
from get_participants.mapping import get_participants_commands

command_map: CommandMapping = {
    # General commands can be added here
} | checkin_commands | get_participants_commands
