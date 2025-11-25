from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ServerConfig:
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_CONFIG = "CONFIG"

        EVENT_MODE = "event_mode"
        ORGANIZER_ROLE = "organizer_role"

    event_mode: str = field(metadata={'db_key': Keys.EVENT_MODE})
    organizer_role: str = field(metadata={'db_key': Keys.ORGANIZER_ROLE})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'ServerConfig':
        return cls(
            event_mode=record.get(cls.Keys.EVENT_MODE),
            organizer_role=record.get(cls.Keys.ORGANIZER_ROLE)
        )
