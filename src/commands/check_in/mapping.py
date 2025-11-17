from commands.models.command_mapping import CommandMapping
import commands.check_in.check_in_commands as check_in_commands

checkin_commands: CommandMapping = {
    "check-in": {
        "function": check_in_commands.check_in_user,
        "description": "Check in the calling user.",
        "params": []
    }
}
