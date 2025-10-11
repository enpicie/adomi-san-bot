from typing import List, Optional

from discord import Embed

import constants

class ResponseMessage:
    content: str
    embeds: Optional[List[Embed]]

    def __init__(self, content: str, embeds: List[Embed] = None):
        self.content = content
        self.embeds = embeds or []

    def to_dict(self) -> dict:
        return {
            "type": constants.DISCORD_INTERACTION_TYPES["MESSAGE_WITH_SOURCE"],
            "data": {
                "content": self.content,
                "embeds": [embed.to_dict() for embed in self.embeds]
            }
        }
