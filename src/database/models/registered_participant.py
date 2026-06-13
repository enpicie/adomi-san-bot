from dataclasses import dataclass
from typing import Any, Dict, Optional

from database.models.participant import Participant

@dataclass
class RegisteredParticipant(Participant):
    class Keys(Participant.Keys):
        SOURCE = "source"
        EXTERNAL_ID = "external_id"

    source: str
    external_id: Optional[str] = None

    def __init__(self, display_name: str, user_id: str, source: str, external_id: Optional[str] = None, time_added: Optional[str] = None):
        super().__init__(display_name, user_id, time_added)

        self.source = source
        self.external_id = external_id

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'RegisteredParticipant':
        return cls(
            display_name=record.get(cls.Keys.DISPLAY_NAME),
            user_id=record.get(cls.Keys.USER_ID),
            source=record.get(cls.Keys.SOURCE),
            external_id=record.get(cls.Keys.EXTERNAL_ID),
            time_added=record.get(cls.Keys.TIME_ADDED)
        )

    def to_dict(self) -> dict:
        base_dict = super().to_dict()

        base_dict["source"] = self.source
        if self.external_id is not None:
            base_dict["external_id"] = self.external_id

        return base_dict
