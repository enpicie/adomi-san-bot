from commands.models.command_mapping import CommandMapping
import commands.check_in.check_in_commands as check_in_commands

checkin_commands: CommandMapping = {
    "check-in": {
        "function": check_in_commands.check_in_user,
        "description": "Check in the calling user and assign Participant role if set",
        "params": []
    },
    "show-check-ins": {
        "function": check_in_commands.show_check_ins,
        "description": "Show list of checked-in users",
        "params": []
    },
    "clear-check-ins": {
        "function": check_in_commands.clear_check_ins,
        "description": "Clear list of checked-in users and remove Participant roles if set",
        "params": []
    }
}
