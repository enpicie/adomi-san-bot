from aws_services import AWSServices

from commands.command_map import command_map
from commands.models.discord_event import DiscordEvent
from commands.models.response_message import ResponseMessage

def process_bot_command(event_body: dict, aws_services: AWSServices) -> dict:
    if "data" not in event_body:
        raise KeyError("No field 'data'. This is not a valid Discord Slash Command message.")

    event = DiscordEvent(event_body)
    command_name = event.get_command_name()

    command = command_map.get(command_name)
    if command is None:
        raise ValueError(f"No command registered for {command_name}")

    command_function = command["function"]
    try:
        message = command_function(event, aws_services)
    except Exception as e:
        print(f"ERROR: Exception while processing command '{command_name}': {e}")
        message = ResponseMessage.get_error_message()
    if message:
        return message.to_dict()

    raise RuntimeError(f"Error processing command '{command_name}': did not return a message.")
