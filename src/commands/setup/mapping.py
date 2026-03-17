from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.setup.server_config_commands as server_config_commands
import commands.setup.show_config_commands as show_config_commands
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

setup_commands: CommandMapping = {
    "setup-server": {
        "function": server_config_commands.setup_server,
        "description": "Set up this server for use with the bot.",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    },
    "set-organizer-role": {
        "function": server_config_commands.set_organizer_role,
        "description": "Set the role for event organizers who can use privileged commands",
        "params": [
            CommandParam(
                name="organizer_role",
                description="Role for event organizers who can use privileged commands",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    },
    "set-default-participant-role": {
        "function": server_config_commands.set_default_participant_role,
        "description": "Set the default role assigned to participants for all events in this server",
        "params": [
            CommandParam(
                name="participant_role",
                description="Default role for event participants to be pinged during events",
                param_type=AppCommandOptionType.role,
                required=True,
                choices=None
            )
        ]
    },
    "show-event-roles": {
        "function": show_config_commands.show_event_roles,
        "description": "Show list of what the event roles in this server are",
        "params": [EVENT_NAME_PARAM]
    }
}
