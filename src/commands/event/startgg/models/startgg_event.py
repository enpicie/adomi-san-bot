from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import commands.event.startgg.source_constants as source_constants
from database.models.participant import Participant
from database.models.registered_participant import RegisteredParticipant


def _unix_to_utc_iso(unix_ts: Optional[int]) -> Optional[str]:
    if unix_ts is None:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class StartggEvent:
    tourney_name: str
    event_name: str
    start_time_utc: Optional[str]
    location: Optional[str]
    participants: List[RegisteredParticipant] = field(default_factory=list)
    no_discord_participants: List[Participant] = field(default_factory=list)

    @classmethod
    def from_dict(cls, event_data: Dict[str, Any]) -> 'StartggEvent':
        """Factory method to create a StartggEvent instance from raw API response data."""
        tournament = event_data.get("tournament", {})
        tourney_name = tournament.get("name", "Unknown Tournament")
        event_name = event_data.get("name", tourney_name)

        start_time_utc = _unix_to_utc_iso(event_data.get("startAt"))

        venue_name = tournament.get("venueName")
        venue_address = tournament.get("venueAddress")
        location = venue_name or venue_address or "Online"

        participants, no_discord_participants = cls._parse_participants(event_data)

        return cls(
            tourney_name=tourney_name,
            event_name=event_name,
            start_time_utc=start_time_utc,
            location=location,
            participants=participants,
            no_discord_participants=no_discord_participants
        )

    @staticmethod
    def _parse_participants(event_data: Dict[str, Any]) -> tuple[List[RegisteredParticipant], List[Participant]]:
        registered_participants: List[RegisteredParticipant] = []
        no_discord_participants: List[Participant] = []

        participants_list = event_data.get("entrants", {}).get("nodes", [])

        for entrant in participants_list:
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
                    user_id=Participant.DEFAULT_ID_PLACEHOLDER
                ))

        return registered_participants, no_discord_participants
