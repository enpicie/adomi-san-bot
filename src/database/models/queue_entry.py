from dataclasses import dataclass
from typing import Dict, Any

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class QueueEntry(SubscriptableMixin):
    """One user's spot in an event's `queue` map (keyed by user_id)."""
    class Keys:
        DISPLAY_NAME = "display_name"
        JOINED_AT = "joined_at"

    display_name: str
    joined_at: int  # epoch milliseconds; queue order is oldest first

    def to_dict(self) -> dict:
        return {
            self.Keys.DISPLAY_NAME: self.display_name,
            self.Keys.JOINED_AT: self.joined_at
        }

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'QueueEntry':
        return cls(
            display_name=record.get(cls.Keys.DISPLAY_NAME) or "",
            # DynamoDB returns numbers as Decimal
            joined_at=int(record.get(cls.Keys.JOINED_AT, 0))
        )
