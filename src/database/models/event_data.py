from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class EventData:
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_SERVER = "SERVER"
        SK_CHANNEL_PREFIX = "CHANNEL#"

        CHECKED_IN = "checked_in"
        REGISTERED = "registered"
        QUEUE = "queue"
        PARTICIPANT_ROLE = "participant_role"

        START_MESSAGE = "start_message"
        END_MESSAGE = "end_message"


    checked_in: dict = field(metadata={'db_key': Keys.CHECKED_IN})
    registered: dict = field(metadata={'db_key': Keys.REGISTERED})
    queue: dict = field(metadata={'db_key': Keys.QUEUE})
    participant_role: str = field(metadata={'db_key': Keys.PARTICIPANT_ROLE})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'EventData':
        return cls(
            checked_in=record.get(cls.Keys.CHECKED_IN),
            registered=record.get(cls.Keys.REGISTERED),
            queue=record.get(cls.Keys.QUEUE),
            participant_role=record.get(cls.Keys.PARTICIPANT_ROLE)
        )
