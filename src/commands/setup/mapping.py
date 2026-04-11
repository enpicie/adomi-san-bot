from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
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
            ),
            CommandParam(
                name="notification_channel",
                description="Channel to post bot notifications in",
                param_type=AppCommandOptionType.channel,
                required=True,
                choices=None
            ),
            CommandParam(
                name="ping_organizers",
                description="Ping the organizer role with notifications (default: False)",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False)
                ]
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
    "setup-notifications": {
        "function": server_config_commands.setup_notifications,
        "description": "Set the channel for bot notifications and whether to ping organizers",
        "params": [
            CommandParam(
                name="channel",
                description="Channel to post bot notifications in",
                param_type=AppCommandOptionType.channel,
                required=True,
                choices=None
            ),
            CommandParam(
                name="ping_organizers",
                description="Ping the organizer role with notifications (default: False)",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False)
                ]
            )
        ]
    },
    "setup-event-reminders": {
        "function": server_config_commands.setup_event_reminders,
        "description": "Configure the announcement channel and default reminder behavior for events",
        "params": [
            CommandParam(
                name="announcement_channel",
                description="Channel to post event reminder announcements in",
                param_type=AppCommandOptionType.channel,
                required=True,
                choices=None
            ),
            CommandParam(
                name="announcement_role",
                description="Role to ping in reminder announcements (leave blank for no ping)",
                param_type=AppCommandOptionType.role,
                required=False,
                choices=None
            ),
            CommandParam(
                name="remind_by_default",
                description="Whether new events should have reminder announcements on by default (default: False)",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False),
                ]
            )
        ]
    },
    "event-view": {
        "function": show_config_commands.event_view,
        "description": "View event settings, toggle states, and participant counts (Organizer only)",
        "params": [EVENT_NAME_PARAM]
    },
    "show-event-roles": {
        "function": show_config_commands.show_event_roles,
        "description": "Show list of what the event roles in this server are",
        "params": [EVENT_NAME_PARAM]
    }
}
