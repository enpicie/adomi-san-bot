from commands.types import CommandMapping

from check_in.mapping import checkin_commands
from get_startgg_attendees.mapping import get_attendees_commands

command_map: CommandMapping = {
    # General commands can be added here
} | checkin_commands | get_attendees_commands
