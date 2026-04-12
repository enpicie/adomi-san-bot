from discord import AppCommandOptionType

from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
import commands.schedule.autocomplete_handlers as autocomplete_handlers
import commands.schedule.schedule_commands as schedule_commands
from commands.event.autocomplete_handlers import autocomplete_event_timezone


schedule_commands_mapping: CommandMapping = {
    "schedule-post": {
        "function": schedule_commands.post_schedule,
        "description": "Post or update the tracked schedule message listing upcoming events (Organizer only)",
        "params": [
            CommandParam(
                name="channel",
                description="Channel to post the schedule in (required when creating a new post)",
                param_type=AppCommandOptionType.channel,
                required=False,
                choices=None,
            ),
            CommandParam(
                name="title",
                description="Header text for the schedule message (default: 'Upcoming Events')",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None,
            ),
            CommandParam(
                name="create_new_post",
                description="Force a new post even if a tracked message already exists (default: False)",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False),
                ],
            ),
        ],
    },
    "schedule-update": {
        "function": schedule_commands.update_schedule,
        "description": "Refresh the tracked schedule message, optionally changing the title (Organizer only)",
        "params": [
            CommandParam(
                name="new_title",
                description="New header text for the schedule message (leave blank to keep current title)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None,
            ),
        ],
    },
    "schedule-plan-event": {
        "function": schedule_commands.add_plan,
        "description": "Add a planned event placeholder to the schedule before creating a Discord event (Organizer only)",
        "params": [
            CommandParam(
                name="name",
                description="Name of the planned event (must match the name used in event-create to auto-remove)",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
            ),
            CommandParam(
                name="start_time",
                description="Format: '2026-03-19 19:30' (24-hour time). Planned start time of the event",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
            ),
            CommandParam(
                name="timezone",
                description="Timezone for the start time",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_event_timezone,
            ),
            CommandParam(
                name="event_link",
                description="Optional link for the event (e.g. start.gg registration page)",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None,
            ),
        ],
    },
    "schedule-plan-remove": {
        "function": schedule_commands.remove_plan,
        "description": "Remove a planned event placeholder from the schedule (Organizer only)",
        "params": [
            CommandParam(
                name="plan_name",
                description="Name of the planned event to remove",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=None,
                autocomplete=True,
                autocomplete_handler=autocomplete_handlers.autocomplete_plan_name,
            ),
        ],
    },
    "schedule-clear-past": {
        "function": schedule_commands.clear_past_plans,
        "description": "Clear all past events from the schedule and refresh the message (Organizer only)",
        "params": [],
    },
}
