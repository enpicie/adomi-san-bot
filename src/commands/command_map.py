from commands.types import CommandMapping

from check_in.mapping import checkin_commands
from retrieve_players.mapping import retrieve_commands

command_map: CommandMapping = {
    # General commands can be added here
} | checkin_commands | retrieve_commands
