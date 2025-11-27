from commands.models.command_mapping import CommandMapping
from commands.models.command_mapping import CommandMapping
from commands.models.command_param import CommandParam
from commands.models.command_param import ParamChoice
from commands.announce import announce_commands
from discord import AppCommandOptionType

announce_commands: CommandMapping = {
    "announce-event": {
        "function": announce_commands.announce_event,
        "description": "Sends the event start OR end announcement for the current event.",
        "params": [
            CommandParam(
                name="announce_type",
                description="Which announcement to send to chat",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[ParamChoice(name="start", value="start"), ParamChoice(
                    name="end", value="end")]
            )
        ]
    },
    "set-event-message": {
        "function": announce_commands.set_event_message,
        "description": "Set announce message. Choose between start or end.",
        "params": [
            CommandParam(
                name="announcement",
                description="Announcement text",
                param_type=AppCommandOptionType.string,
                required=False,
                choices=None
            ),
            CommandParam(
                name="announce_type",
                description="Choose which announcement to set; start or end.",
                param_type=AppCommandOptionType.string,
                required=True,
                choices=[ParamChoice(name="start", value="start"), ParamChoice(
                    name="end", value="end")]
            ),
        ]
    }
}
