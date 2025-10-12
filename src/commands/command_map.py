from commands.models.command_mapping import CommandMapping

from commands.check_in.mapping import checkin_commands
from commands.config.mapping import config_commands

command_map: CommandMapping = {
} | checkin_commands | config_commands
