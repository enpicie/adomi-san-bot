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
        SERVER_NAME = "server_name"
        ORGANIZER_ROLE = "organizer_role"
        DEFAULT_PARTICIPANT_ROLE = "default_participant_role"
        NOTIFICATION_CHANNEL_ID = "notification_channel_id"
        PING_ORGANIZERS = "ping_organizers"
        STARTGG_OAUTH_TOKEN = "oauth_token_startgg"

        ANNOUNCEMENT_CHANNEL_ID = "announcement_channel_id"
        ANNOUNCEMENT_ROLE_ID = "announcement_role_id"
        SHOULD_ALWAYS_REMIND = "should_always_remind"

    server_id: str = field(metadata={'db_key': Keys.SERVER_ID})
    server_name: str = field(metadata={'db_key': Keys.SERVER_NAME})
    organizer_role: str = field(metadata={'db_key': Keys.ORGANIZER_ROLE})
    default_participant_role: str = field(metadata={'db_key': Keys.DEFAULT_PARTICIPANT_ROLE})
    notification_channel_id: Optional[str] = field(default=None, metadata={'db_key': Keys.NOTIFICATION_CHANNEL_ID})
    ping_organizers: Optional[bool] = field(default=False, metadata={'db_key': Keys.PING_ORGANIZERS})
    startgg_oauth_token: Optional[str] = field(default=None, metadata={'db_key': Keys.STARTGG_OAUTH_TOKEN})
    announcement_channel_id: Optional[str] = field(default=None, metadata={'db_key': Keys.ANNOUNCEMENT_CHANNEL_ID})
    announcement_role_id: Optional[str] = field(default=None, metadata={'db_key': Keys.ANNOUNCEMENT_ROLE_ID})
    should_always_remind: Optional[bool] = field(default=False, metadata={'db_key': Keys.SHOULD_ALWAYS_REMIND})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'ServerConfig':
        return cls(
            server_id=record[cls.Keys.SERVER_ID],
            server_name=record.get(cls.Keys.SERVER_NAME),
            organizer_role=record.get(cls.Keys.ORGANIZER_ROLE),
            default_participant_role=record.get(cls.Keys.DEFAULT_PARTICIPANT_ROLE),
            notification_channel_id=record.get(cls.Keys.NOTIFICATION_CHANNEL_ID),
            ping_organizers=record.get(cls.Keys.PING_ORGANIZERS, False),
            startgg_oauth_token=record.get(cls.Keys.STARTGG_OAUTH_TOKEN),
            announcement_channel_id=record.get(cls.Keys.ANNOUNCEMENT_CHANNEL_ID),
            announcement_role_id=record.get(cls.Keys.ANNOUNCEMENT_ROLE_ID),
            should_always_remind=record.get(cls.Keys.SHOULD_ALWAYS_REMIND, False),
        )
