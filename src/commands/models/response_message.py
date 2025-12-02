from typing import Dict, List, Optional
from discord import Embed

import constants
import utils.adomin_messages as adomin_messages

# https://discord.com/developers/docs/resources/message#message-object-message-flags
SUPPRESS_EMBEDS_FLAG = 1 << 2

class ResponseMessage:
    content: str
    embeds: Optional[List[Embed]]
    allowed_mentions: Optional[Dict] = None
    flags: Optional[int] = None

    def __init__(self, content: str, embeds: List[Embed] = None):
        self.content = content
        self.embeds = embeds or []

    def with_silent_pings(self) -> "ResponseMessage":
        self.allowed_mentions = {
            "parse": [] # Disable all automatic pings
        }
        return self

    def with_suppressed_embeds(self) -> "ResponseMessage":
        self.flags = SUPPRESS_EMBEDS_FLAG
        return self

    def to_dict(self) -> dict:
        data = {
            "content": self.content,
            "embeds": [embed.to_dict() for embed in self.embeds]
        }

        if self.allowed_mentions is not None: # Set when silencing mentions
            data["allowed_mentions"] = self.allowed_mentions
            data["content"] = "@silent " + data["content"] # Will show with silent bell in discord
        if self.flags is not None:
            data["flags"] = self.flags

        return {
            "type": constants.DISCORD_CALLBACK_TYPES["MESSAGE_WITH_SOURCE"],
            "data": data
        }

    @staticmethod
    def get_error_message() -> "ResponseMessage":
        return ResponseMessage(content=adomin_messages.GENERAL_ERROR)
