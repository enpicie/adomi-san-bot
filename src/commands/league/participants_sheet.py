from enum import IntEnum
from typing import List


class ParticipantsColumn(IntEnum):
    STATUS = 0
    DISCORD_ID = 1
    PARTICIPANT_NAME = 2
    TIER = 3
    RANK = 4
    NOTES = 5


COLUMN_HEADERS: List[str] = [
    "Status",
    "Discord ID (@)",
    "Participant Name",
    "Tier",
    "Rank",
    "Notes",
]

SHEET_NAME = "Participants"
SHEET_RANGE = f"{SHEET_NAME}!A:F"
STATUS_QUEUED = "QUEUED"
STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"
