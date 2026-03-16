from dataclasses import dataclass, field
from typing import Dict, Any

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class ServerConfig(SubscriptableMixin):
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_CONFIG = "CONFIG"

        SERVER_ID = "server_id"
        ORGANIZER_ROLE = "organizer_role"

    organizer_role: str = field(metadata={'db_key': Keys.ORGANIZER_ROLE})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'ServerConfig':
        return cls(
            organizer_role=record.get(cls.Keys.ORGANIZER_ROLE)
        )
