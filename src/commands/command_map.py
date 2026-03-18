from commands.models.command_mapping import CommandMapping

from commands.help.mapping import help_commands
from commands.check_in.mapping import checkin_commands
from commands.setup.mapping import setup_commands
from commands.register.mapping import register_commands_mapping
from commands.event.mapping import event_commands_mapping

command_map: CommandMapping = {
} | (
    help_commands |
    checkin_commands |
    setup_commands |
    register_commands_mapping |
    event_commands_mapping
)
