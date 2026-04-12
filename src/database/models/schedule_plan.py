from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class SchedulePlan:
    class Keys:
        SK_PLAN_PREFIX = "SCHEDULE_PLAN#"
        PLAN_NAME = "plan_name"
        START_TIME = "start_time"
        EVENT_LINK = "event_link"

    plan_name: str
    start_time: str  # UTC ISO 8601
    event_link: Optional[str] = None

    @staticmethod
    def normalize_name(name: str) -> str:
        return name.strip().lower()

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'SchedulePlan':
        return cls(
            plan_name=record[cls.Keys.PLAN_NAME],
            start_time=record[cls.Keys.START_TIME],
            event_link=record.get(cls.Keys.EVENT_LINK),
        )
