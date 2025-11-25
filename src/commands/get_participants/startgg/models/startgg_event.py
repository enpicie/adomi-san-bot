from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from get_participants.startgg.models.startgg_participant import StartggParticipant

def _parse_participants(event_data: Dict[str, Any]) -> List[StartggParticipant]:
    """Parses raw entrants data into a list of StartggParticipant objects."""

    # Use .get() defensively in case 'entrants' or 'nodes' is missing
    participants_list = event_data.get("entrants", {}).get("nodes", [])
    parsed_participants: List[StartggParticipant] = []

    for entrant in participants_list:
        # Check if participants list exists and is non-empty
        participant_data: Optional[Dict[str, Any]] = entrant.get("participants", [None])[0]

        if participant_data is None:
            continue

        participant = StartggParticipant(
            startgg_id=participant_data.get("id"),
            username=participant_data.get("gamerTag")
        )
        authorizations = participant_data.get("user", {}).get("authorizations")
        # See startgg_graphl.py to see query looks only for Discord authorizations
        if authorizations and authorizations[0]:
            discord_auth = authorizations[0]
            participant.discord_id = discord_auth.get("externalId")
            participant.discord_user = discord_auth.get("externalUsername")

        parsed_participants.append(participant)

    return parsed_participants

@dataclass
class StartggEvent:
    tourney_name: str
    participants: List[StartggParticipant] = field(default_factory=list)

    @classmethod
    def from_dict(cls, event_data: Dict[str, Any]) -> 'StartggEvent':
        """Factory method to create a StartggEvent instance from raw API response data."""

        # Safely extract tourney name
        tourney_name = event_data.get("tournament", {}).get("name", "Unknown Tournament")

        # Delegate complex parsing to the standalone helper function
        participants = _parse_participants(event_data)

        return cls(tourney_name=tourney_name, participants=participants)
