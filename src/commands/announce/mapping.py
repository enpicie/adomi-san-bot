from commands.models.command_mapping import CommandMapping
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
from commands.models.command_param import ParamChoice
from commands.announce import announce_commands
from discord import AppCommandOptionType

announce_commands: CommandMapping = {
    "announce-event": {
        "function": announce_commands.announce_event,
        "description": "Sends the announcement message to signal start or end of the current event",
        "params": [
            CommandParam(
                name="announce_type",
                description="Determines whether start or end announcement is sent to chat",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(
                        name="start",
                        value="start"
                    ), 
                    ParamChoice(
                        name="end", 
                        value="end"
                    )
                ]
            ),
            CommandParam(
                name="ping_participants",
                description="Determines whether or not to ping event participants in the announcement",
                param_type=AppCommandOptionType.boolean,
                required=True,
                choices=None
            ),
        ]
    },
    "set-event-message": {
        "function": announce_commands.set_event_message,
        "description": "Set event announcement message",
        "params": [
            CommandParam(
                name="message_text",
                description="Text sent in announcement message",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="announce_type",
                description="Choose which announcement to set: start or end.",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[
                    ParamChoice(
                        name="start",
                        value="start"
                    ), 
                    ParamChoice(
                        name="end", 
                        value="end"
                    )
                ]
            ),
        ]
    }
}
