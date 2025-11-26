from dataclasses import dataclass
from typing import Optional

from database.models.participant import Participant

@dataclass
class RegisteredParticipant(Participant):
    NO_DISCORD_ID_IDENTIFIER = "no_id"

    class Keys(Participant.Keys):
        SOURCE = "source"
        EXTERNAL_ID = "external_id"

    source: str
    external_id: Optional[str] = None # Make external_id optional with a default of None

    def __init__(self, display_name: str, user_id: str, source: str, external_id: Optional[str] = None):
        super().__init__(display_name, user_id)

        self.source = source
        self.external_id = external_id

    def to_dict(self) -> dict:
        base_dict = super().to_dict()

        base_dict["source"] = self.source
        # Only include external_id if it's not None
        if self.external_id is not None:
            base_dict["external_id"] = self.external_id

        return base_dict
