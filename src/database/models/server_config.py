from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class ServerConfig(SubscriptableMixin):
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_CONFIG = "CONFIG"

        SERVER_ID = "server_id"
        ORGANIZER_ROLE = "organizer_role"
        DEFAULT_PARTICIPANT_ROLE = "default_participant_role"
        NOTIFICATION_CHANNEL_ID = "notification_channel_id"
        PING_ORGANIZERS = "ping_organizers"

    server_id: str = field(metadata={'db_key': Keys.SERVER_ID})
    organizer_role: str = field(metadata={'db_key': Keys.ORGANIZER_ROLE})
    default_participant_role: str = field(metadata={'db_key': Keys.DEFAULT_PARTICIPANT_ROLE})
    notification_channel_id: Optional[str] = field(default=None, metadata={'db_key': Keys.NOTIFICATION_CHANNEL_ID})
    ping_organizers: Optional[bool] = field(default=False, metadata={'db_key': Keys.PING_ORGANIZERS})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'ServerConfig':
        return cls(
            server_id=record[cls.Keys.SERVER_ID],
            organizer_role=record.get(cls.Keys.ORGANIZER_ROLE),
            default_participant_role=record.get(cls.Keys.DEFAULT_PARTICIPANT_ROLE),
            notification_channel_id=record.get(cls.Keys.NOTIFICATION_CHANNEL_ID),
            ping_organizers=record.get(cls.Keys.PING_ORGANIZERS, False)
        )
