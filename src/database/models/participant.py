from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

@dataclass
class Participant:
    DEFAULT_ID_PLACEHOLDER = "no_id"

    class Keys:
        DISPLAY_NAME = "display_name"
        USER_ID = "user_id"
        TIME_ADDED = "time_added"

    display_name: str
    user_id: str
    time_added: str # ISO format UTC timestamp

    def __init__(self, display_name: str, user_id: str, time_added: str = None):
        self.display_name = display_name
        self.user_id = user_id
        self.time_added = (
            # e.g. '2025-11-16T14:23:45Z'
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            if time_added is None
            else time_added
        )


    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "user_id": self.user_id,
            "time_added": self.time_added
        }

    def __eq__(self, other):
        if isinstance(other, Participant):
            return self.user_id == other.user_id
        return NotImplemented

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'Participant':
        return cls(
            display_name=record.get(cls.Keys.DISPLAY_NAME),
            user_id=record.get(cls.Keys.USER_ID),
            time_added=record.get(cls.Keys.TIME_ADDED)
        )

    def _get_datetime_object(self) -> datetime:
        """Helper to safely convert the stored ISO string back to a datetime object with UTC timezone."""
        iso_str = self.time_added
        if iso_str.endswith('Z'):
            iso_str = iso_str.replace('Z', '+00:00')
        # Use fromisoformat and ensure it's timezone-aware (as stored)
        return datetime.fromisoformat(iso_str)

    def get_readable_time_added(self) -> str:
        """Returns time_added as a standard readable date/time string (e.g., 'Nov 28, 2025, 14:23 UTC')."""
        try:
            dt = self._get_datetime_object()
            return dt.strftime('%b %d, %Y, %H:%M UTC')
        except Exception:
            return self.time_added

    def get_relative_time_added(self) -> str:
        """
        Returns a human-readable, relative string for when the participant was added
        (e.g., 'Just now', '5 minutes ago', 'Yesterday', or 'On Nov 28, 2025').
        This is the cleanest and most natural way to display time to users.
        """
        try:
            now = datetime.now(timezone.utc)
            dt = self._get_datetime_object()
            delta: timedelta = now - dt

            if delta < timedelta(minutes=1):
                return "Just now"
            if delta < timedelta(hours=1):
                minutes = int(delta.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            if delta < timedelta(days=1):
                hours = int(delta.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            if delta < timedelta(days=2) and now.day != dt.day:
                 return "Yesterday"

            return f"On {dt.strftime('%b %d, %Y')}"

        except Exception:
            # Fallback to basic readable time
            return self.get_readable_time_added()
