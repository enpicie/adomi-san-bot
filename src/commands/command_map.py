from commands.models.command_mapping import CommandMapping

from commands.check_in.mapping import checkin_commands

command_map: CommandMapping = {
    # General commands can be added here
} | checkin_commands
