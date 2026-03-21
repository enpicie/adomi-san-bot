from enum import IntEnum
from typing import List


class ParticipantsColumn(IntEnum):
    STATUS = 0
    DISCORD_ID = 1
    PARTICIPANT_NAME = 2
    TIER = 3
    GROUP_NUMBER = 4
    GROUP_RANK = 5
    NOTES = 6
    WINS_ROW = 7
    LOSSES_COL = 8


COLUMN_HEADERS: List[str] = [
    "Status",
    "Discord ID (@)",
    "Participant Name",
    "Tier",
    "Group #",
    "Group Rank",
    "Notes",
    "Wins Row",
    "Losses Col",
]

SHEET_NAME = "Participants"
SHEET_RANGE = f"{SHEET_NAME}!A:I"

# Metadata cells in row 1 only — not participant data columns
CURRENT_ROTATION_LABEL = "Current Rotation:"
CURRENT_ROTATION_LABEL_COL = 9   # Column J
CURRENT_ROTATION_VALUE_COL = 10  # Column K

STATUS_QUEUED = "QUEUED"
STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"
STATUS_DNF = "DNF"

ALL_STATUSES = [STATUS_ACTIVE, STATUS_QUEUED, STATUS_INACTIVE, STATUS_DNF]
