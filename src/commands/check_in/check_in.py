import utils.message_helper as msg_helper
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def check_in_user(event: DiscordEvent) -> ResponseMessage:
    user_id = event.get_user_id()
    return ResponseMessage(content=f"Checked in {msg_helper.get_user_ping(user_id)}!")

