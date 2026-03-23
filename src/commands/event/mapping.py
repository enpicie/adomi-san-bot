from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
import commands.event.event_commands as event_commands
import commands.event.autocomplete_handlers as autocomplete_handlers
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

event_commands_mapping: CommandMapping = {
    "event-create": {
        "function": event_commands.create_event,
        "description": "Create a new event and register it with the bot",
        "params": [
            CommandParam(
                name="event_name",
                description="Name of the event",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="event_location",
                description="Location of the event",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="start_time",
                description="Format: '2026-03-19 19:30' (24-hour time, year required). Date and time the event starts",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="end_time",
                description="Format: '2026-03-19 21:30' (24-hour time, year required). Date and time the event ends",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="timezone",
                description="Timezone of the event",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_event_timezone
            ),
            CommandParam(
                name="event_description",
                description="Description of the event",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="participant_role",
                description="Role for participants. Defaults to server default if not provided.",
                param_type=AppCommandOptionType.role,
                required=False,
                choices=None
            )
        ]
    },
    "event-update": {
        "function": event_commands.update_event,
        "description": "Update an existing event's details",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="new_name",
                description="New name for the event (leave blank to keep current name)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="event_location",
                description="Location of the event (leave blank to keep current)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="start_time",
                description="Format: 'YYYY-MM-DD HH:MM' (24-hr). Leave blank to keep current start time.",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="end_time",
                description="Format: 'YYYY-MM-DD HH:MM' (24-hr). Leave blank to keep current end time.",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="timezone",
                description="Timezone for start/end time (required if providing start_time or end_time)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_event_timezone
            ),
            CommandParam(
                name="event_description",
                description="Description of the event",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="participant_role",
                description="Role for participants. Defaults to server default if not provided.",
                param_type=AppCommandOptionType.role,
                required=False,
                choices=None
            )
        ]
    },
    "event-delete": {
        "function": event_commands.delete_event,
        "description": "Delete an event and remove it from the bot",
        "params": [
            CommandParam(
                name="event_name",
                description="Name of the event to delete",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_event_name
            )
        ]
    },
    "event-create-startgg": {
        "function": event_commands.create_event_startgg,
        "description": "Create an event and import registered participants from a start.gg Tournament Event",
        "params": [
            CommandParam(
                name="event_link",
                description="Link to a start.gg Tournament Event (ex: start.gg/tournament/midweek-melting/event/mbaacc-bracket)",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="end_time",
                description="Format: '2026-03-19 21:30'. End time — event data cleaned up after this",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="timezone",
                description="Timezone for the end time",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_event_timezone
            ),
            CommandParam(
                name="participant_role",
                description="Role for participants. Defaults to server default if not provided.",
                param_type=AppCommandOptionType.role,
                required=False,
                choices=None
            )
        ]
    },
    "event-update-startgg": {
        "function": event_commands.update_event_startgg,
        "description": "Link an existing event to a start.gg Tournament Event and refresh its data",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="event_link",
                description="Link to a start.gg Tournament Event (ex: start.gg/tournament/midweek-melting/event/mbaacc-bracket)",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="end_time",
                description="Format: '2026-03-19 21:30'. End time — event data cleaned up after this",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None
            ),
            CommandParam(
                name="timezone",
                description="Timezone for the end time",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_event_timezone
            ),
            CommandParam(
                name="participant_role",
                description="Role for participants. Defaults to server default if not provided.",
                param_type=AppCommandOptionType.role,
                required=False,
                choices=None
            )
        ]
    },
    "event-refresh-startgg": {
        "function": event_commands.event_refresh_startgg,
        "description": "Refresh registered participants for an existing event from its linked start.gg event",
        "params": [EVENT_NAME_PARAM]
    },
    "event-list": {
        "function": event_commands.events_list,
        "description": "List all events for this server",
        "params": []
    }
}
