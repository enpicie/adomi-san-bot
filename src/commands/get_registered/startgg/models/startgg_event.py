from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

import commands.get_registered.source_constants as source_constants
from database.models.participant import Participant
from database.models.registered_participant import RegisteredParticipant

@dataclass
class StartggEvent:
    tourney_name: str
    participants: List[RegisteredParticipant] = field(default_factory=list)
    no_discord_participants: List[Participant] = field(default_factory=list)

    @classmethod
    def from_dict(cls, event_data: Dict[str, Any]) -> 'StartggEvent':
        """Factory method to create a StartggEvent instance from raw API response data."""

        # Safely extract tourney name
        tourney_name = event_data.get("tournament", {}).get("name", "Unknown Tournament")

        participants, no_discord_participants = cls._parse_participants(event_data)

        return cls(
            tourney_name=tourney_name,
            participants=participants,
            no_discord_participants=no_discord_participants
        )

    @staticmethod
    def _parse_participants(event_data: Dict[str, Any]) -> tuple[List[RegisteredParticipant], List[Participant]]:
        registered_participants: List[RegisteredParticipant] = []
        no_discord_participants: List[Participant] = []

        participants_list = event_data.get("entrants", {}).get("nodes", [])

        for entrant in participants_list:
            # Check if participants list exists and is non-empty
            participant_data: Optional[Dict[str, Any]] = entrant.get("participants", [None])[0]

            if participant_data is None:
                continue

            startgg_name = participant_data.get("gamerTag")
            authorizations = participant_data.get("user", {}).get("authorizations")

            if authorizations and authorizations[0]:
                discord_auth = authorizations[0]
                registered_participants.append(RegisteredParticipant(
                    display_name=startgg_name,
                    user_id=discord_auth.get("externalId"),
                    source=source_constants.STARTGG,
                    external_id=participant_data.get("id")
                ))
            else:
                no_discord_participants.append(Participant(
                    display_name=startgg_name,
                    user_id="no_id"
                ))

        return registered_participants, no_discord_participants

