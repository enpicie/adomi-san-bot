from discord import AppCommandOptionType

import commands.queue.queue_constants as queue_constants
import commands.queue.queue_commands as queue_commands
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam, ParamChoice
from commands.event.autocomplete_handlers import EVENT_NAME_PARAM

queue_commands_mapping: CommandMapping = {
    "queue-join": {
        "function": queue_commands.join_queue,
        "description": "Join the queue for an event",
        "params": [EVENT_NAME_PARAM]
    },
    "queue-leave": {
        "function": queue_commands.leave_queue,
        "description": "Leave the queue for an event",
        "params": [EVENT_NAME_PARAM]
    },
    "queue-view": {
        "function": queue_commands.view_queue,
        "description": "Show the queue for an event in order, optionally ping everyone in it",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="ping_users",
                description="Set to 'True' to ping everyone in the queue (Organizer only, default: 'False')",
                param_type=AppCommandOptionType.boolean,
                required=False,
                choices=[
                    ParamChoice(name="True", value=True),
                    ParamChoice(name="False", value=False)
                ]
            )
        ]
    },
    "queue-toggle": {
        "function": queue_commands.toggle_queue,
        "description": "Open or close joining the queue for an event (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="state",
                description="Set to 'Start' to let players join, and set to 'End' to stop new joins",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(name="Start", value=queue_constants.START_PARAM),
                    ParamChoice(name="End", value=queue_constants.END_PARAM)
                ]
            )
        ]
    },
    "queue-pop": {
        "function": queue_commands.pop_queue,
        "description": "Take players off the front of the queue and ping them (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="count",
                description=f"How many players to take (default: 1, max: {queue_constants.MAX_POP_COUNT})",
                param_type=AppCommandOptionType.integer,
                required=False,
                choices=None
            )
        ]
    },
    "queue-remove": {
        "function": queue_commands.remove_from_queue,
        "description": "Remove a user from the queue for an event (Organizer only)",
        "params": [
            EVENT_NAME_PARAM,
            CommandParam(
                name="user",
                description="The user to remove from the queue",
                param_type=AppCommandOptionType.user,
                required=True,
                choices=None
            )
        ]
    },
    "queue-clear": {
        "function": queue_commands.clear_queue,
        "description": "Remove everyone from the queue for an event (Organizer only)",
        "params": [EVENT_NAME_PARAM]
    }
}
