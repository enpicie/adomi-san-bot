from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class Participant:
    display_name: str
    user_id: str
    time_added: str # ISO format UTC timestamp

    def __init__(self, display_name: str, user_id: str):
        self.display_name = display_name
        self.user_id = user_id
        # e.g. '2025-11-16T14:23:45Z'
        self.time_added = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "user_id": self.user_id
        }

    def __eq__(self, other):
        if isinstance(other, Participant):
            return self.user_id == other.user_id
        return NotImplemented
