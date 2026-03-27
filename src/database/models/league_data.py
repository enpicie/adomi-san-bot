from dataclasses import dataclass, field
from typing import Dict, Any

from database.models.subscriptable_mixin import SubscriptableMixin

@dataclass
class LeagueData(SubscriptableMixin):
    class Keys:
        PK_FIELD = "pk"
        SK_FIELD = "sk"
        SK_LEAGUE_PREFIX = "LEAGUE#"
        SERVER_ID = "server_id"
        GOOGLE_SHEETS_LINK = "google_sheets_link"

        LEAGUE_NAME = "league_name"
        LEAGUE_ID = "league_id"

        ACTIVE_PLAYERS = "active_players"
        QUEUED_PARTICIPANTS = "queued_participants"
        ACTIVE_PARTICIPANT_ROLE = "active_participant_role"
        JOIN_ENABLED = "join_enabled"
        REPORT_ENABLED = "report_enabled"


    google_sheets_link: str = field(metadata={'db_key': Keys.GOOGLE_SHEETS_LINK})
    league_name: str = field(metadata={'db_key': Keys.LEAGUE_NAME})
    league_id: str = field(metadata={'db_key': Keys.LEAGUE_ID})
    active_players: dict = field(metadata={'db_key': Keys.ACTIVE_PLAYERS})
    join_enabled: bool = field(metadata={'db_key': Keys.JOIN_ENABLED})
    report_enabled: bool = field(metadata={'db_key': Keys.REPORT_ENABLED})
    active_participant_role: str | None = field(default=None, metadata={'db_key': Keys.ACTIVE_PARTICIPANT_ROLE})
    queued_participants: dict = field(default_factory=dict, metadata={'db_key': Keys.QUEUED_PARTICIPANTS})

    @classmethod
    def from_dynamodb(cls, record: Dict[str, Any]) -> 'LeagueData':
        return cls(
            google_sheets_link=record.get(cls.Keys.GOOGLE_SHEETS_LINK),
            league_name=record.get(cls.Keys.LEAGUE_NAME),
            league_id=record.get(cls.Keys.LEAGUE_ID),
            active_players=record.get(cls.Keys.ACTIVE_PLAYERS, {}),
            join_enabled=record.get(cls.Keys.JOIN_ENABLED, False),
            report_enabled=record.get(cls.Keys.REPORT_ENABLED, False),
            active_participant_role=record.get(cls.Keys.ACTIVE_PARTICIPANT_ROLE),
            queued_participants=record.get(cls.Keys.QUEUED_PARTICIPANTS, {}),
        )
