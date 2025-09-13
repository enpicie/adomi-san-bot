from commands.types import CommandMapping
import check_in.check_in as check_in

checkin_commands: CommandMapping = {
    "check-in": {
        "function": check_in.check_in_user,
        "description": "Check in the calling user.",
        "params": []
    }
}
