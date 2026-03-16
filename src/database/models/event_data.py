from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class EventData(SubscriptableMixin):
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_EVENT_PREFIX = "EVENT#"
        SERVER_ID = "server_id"
        EVENT_ID = "event_id"

        EVENT_NAME = "event_name"
        EVENT_LOCATION = "event_location"
        START_TIME = "start_time"
        END_TIME = "end_time"

        CHECKED_IN = "checked_in"
        REGISTERED = "registered"
        QUEUE = "queue"
        PARTICIPANT_ROLE = "participant_role"
        CHECK_IN_ENABLED = "check_in_enabled"
        REGISTER_ENABLED = "register_enabled"

        START_MESSAGE = "start_message"
        END_MESSAGE = "end_message"
        STARTGG_URL = "startgg_url"


    checked_in: dict = field(metadata={'db_key': Keys.CHECKED_IN})
    registered: dict = field(metadata={'db_key': Keys.REGISTERED})
    queue: dict = field(metadata={'db_key': Keys.QUEUE})
    participant_role: str = field(metadata={'db_key': Keys.PARTICIPANT_ROLE})
    check_in_enabled: bool = field(metadata={'db_key': Keys.CHECK_IN_ENABLED})
    register_enabled: bool = field(metadata={'db_key': Keys.REGISTER_ENABLED})
    start_message: str = field(metadata={'db_key': Keys.START_MESSAGE})
    end_message: str = field(metadata={'db_key': Keys.END_MESSAGE})
    startgg_url: Optional[str] = field(default=None, metadata={'db_key': Keys.STARTGG_URL})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'EventData':
        return cls(
            checked_in=record.get(cls.Keys.CHECKED_IN),
            registered=record.get(cls.Keys.REGISTERED),
            queue=record.get(cls.Keys.QUEUE),
            participant_role=record.get(cls.Keys.PARTICIPANT_ROLE),
            check_in_enabled=record.get(cls.Keys.CHECK_IN_ENABLED),
            register_enabled=record.get(cls.Keys.REGISTER_ENABLED),
            start_message=record.get(cls.Keys.START_MESSAGE),
            end_message=record.get(cls.Keys.END_MESSAGE),
            startgg_url=record.get(cls.Keys.STARTGG_URL)
        )
