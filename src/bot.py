from discord import Message

import constants
from commands.command_map import command_map

def process_bot_command(event_body: dict) -> dict:
    if "data" not in event_body:
        raise KeyError("No field 'data'. This is not a valid Discord Slash Command message.")

    command_name = event_body.get("data", {}).get("name")
    if command_name is None:
        raise ValueError("Missing 'name' field in event body")

    command = command_map.get(command_name)
    if command is None:
        raise ValueError(f"No command registered for {command_name}")
    message = command["function"](event_body)
    if message:
        return message.to_dict()

    raise RuntimeError(f"Error processing command '{command_name}': did not return a message.")
