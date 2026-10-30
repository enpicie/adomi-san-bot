from dataclasses import dataclass
from typing import Dict, Any

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class ScoreEntry(SubscriptableMixin):
    """One player's row in an event's `scores` map (keyed by user_id)."""
    class Keys:
        DISPLAY_NAME = "display_name"
        SCORE = "score"

    display_name: str
    score: int

    def to_dict(self) -> dict:
        return {
            self.Keys.DISPLAY_NAME: self.display_name,
            self.Keys.SCORE: self.score
        }

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'ScoreEntry':
        return cls(
            display_name=record.get(cls.Keys.DISPLAY_NAME) or "",
            # DynamoDB returns numbers as Decimal
            score=int(record.get(cls.Keys.SCORE, 0))
        )
