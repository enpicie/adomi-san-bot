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

        SHOULD_POST_REMINDER = "should_post_reminder"
        DID_POST_REMINDER = "did_post_reminder"
        REMINDER_ROLE_ID = "reminder_role_id"


    checked_in: dict = field(metadata={'db_key': Keys.CHECKED_IN})
    registered: dict = field(metadata={'db_key': Keys.REGISTERED})
    queue: dict = field(metadata={'db_key': Keys.QUEUE})
    participant_role: str = field(metadata={'db_key': Keys.PARTICIPANT_ROLE})
    check_in_enabled: bool = field(metadata={'db_key': Keys.CHECK_IN_ENABLED})
    register_enabled: bool = field(metadata={'db_key': Keys.REGISTER_ENABLED})
    start_message: str = field(metadata={'db_key': Keys.START_MESSAGE})
    end_message: str = field(metadata={'db_key': Keys.END_MESSAGE})
    start_time: Optional[str] = field(default=None, metadata={'db_key': Keys.START_TIME})
    end_time: Optional[str] = field(default=None, metadata={'db_key': Keys.END_TIME})
    event_location: Optional[str] = field(default=None, metadata={'db_key': Keys.EVENT_LOCATION})
    event_name: Optional[str] = field(default=None, metadata={'db_key': Keys.EVENT_NAME})
    startgg_url: Optional[str] = field(default=None, metadata={'db_key': Keys.STARTGG_URL})
    should_post_reminder: Optional[bool] = field(default=False, metadata={'db_key': Keys.SHOULD_POST_REMINDER})
    did_post_reminder: Optional[bool] = field(default=False, metadata={'db_key': Keys.DID_POST_REMINDER})
    reminder_role_id: Optional[str] = field(default=None, metadata={'db_key': Keys.REMINDER_ROLE_ID})

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
            start_time=record.get(cls.Keys.START_TIME),
            end_time=record.get(cls.Keys.END_TIME),
            event_location=record.get(cls.Keys.EVENT_LOCATION),
            event_name=record.get(cls.Keys.EVENT_NAME),
            startgg_url=record.get(cls.Keys.STARTGG_URL),
            should_post_reminder=record.get(cls.Keys.SHOULD_POST_REMINDER, False),
            did_post_reminder=record.get(cls.Keys.DID_POST_REMINDER, False),
            reminder_role_id=record.get(cls.Keys.REMINDER_ROLE_ID),
        )
