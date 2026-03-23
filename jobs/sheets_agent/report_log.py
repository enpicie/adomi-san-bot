from enum import IntEnum
from typing import List


class ReportLogColumn(IntEnum):
    LEAGUE_ID = 0
    TIER = 1
    GROUP = 2
    WINNER = 3
    LOSER = 4
    WINNER_SCORE = 5
    LOSER_SCORE = 6
    TIMESTAMP = 7


SHEET_NAME = "ReportLog"

COLUMN_HEADERS: List[str] = [
    "LeagueID",
    "Tier",
    "Group",
    "Winner",
    "Loser",
    "WinnerScore",
    "LoserScore",
    "Timestamp",
]

SHEET_RANGE = f"{SHEET_NAME}!A:H"
