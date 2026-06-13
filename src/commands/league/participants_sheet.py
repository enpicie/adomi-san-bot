# MIRROR: jobs/sheets_agent/participants_sheet.py — keep in sync (independent Lambda packaging).
# NOTE: the jobs copy has extra columns and SHEET_RANGE differs (A:I vs A:G) — verify before syncing.
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


COLUMN_HEADERS: List[str] = [
    "Status",
    "Discord ID (@)",
    "Participant Name",
    "Tier",
    "Group #",
    "Group Rank",
    "Notes",
]

SHEET_NAME = "Participants"
SHEET_RANGE = f"{SHEET_NAME}!A:G"
STATUS_QUEUED = "QUEUED"
STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"
STATUS_DNF = "DNF"
