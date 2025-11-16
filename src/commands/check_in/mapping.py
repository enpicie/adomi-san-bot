from commands.models.command_mapping import CommandMapping
import commands.check_in.commands as commands

checkin_commands: CommandMapping = {
    "check-in": {
        "function": commands.check_in_user,
        "description": "Check in the calling user.",
        "params": []
    }
}
