from discord import Message

import constants
from commands.command_map import command_map
from commands.models.command_mapping import CommandEntry

def serialize_message(message: Message) -> dict:
    return {
        "type": constants.DISCORD_RESPONSE_TYPES["MESSAGE_WITH_SOURCE"],
        "content": message.content,
        "embeds": [embed.to_dict() for embed in message.embeds] if message.embeds else [],
        "attachments": [attachment.to_dict() for attachment in message.attachments] if message.attachments else [],
        "allowed_mentions": message.allowed_mentions.to_dict() if message.allowed_mentions else {}
    }

def process_bot_command(event_body: dict) -> dict:
    if "data" not in event_body:
        raise KeyError("No field 'data'. This is not a valid Discord Slash Command message.")

    command_name = event_body.get("data", {}).get("name")
    if command_name is None:
        raise ValueError("Missing 'name' field in event body")

    command: CommandEntry | None = command_map.get(command_name)
    if command is None:
        raise ValueError(f"No command registered for {command_name}")
    message = command.function(event_body)
    if message:
        return serialize_message(message)

    raise RuntimeError(f"Error processing command '{command_name}': did not return a message.")
