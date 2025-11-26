from typing import List

from database.models.participant import Participant

def get_user_ping(user_id: str) -> str:
    return f"<@{user_id}>"

def get_channel_mention(channel_id: str) -> str:
    return f"<#{channel_id}>"

def build_participants_list(list_header: str, participants: List[Participant]) -> str:
    list_lines = (
        f"- {p[Participant.Keys.DISPLAY_NAME]}"
        if p[Participant.Keys.USER_ID] == Participant.DEFAULT_ID_PLACEHOLDER
        else f"- {get_user_ping(p[Participant.Keys.USER_ID])}"
        for p in participants
    )

    return (
        f"{list_header}\n"
        + "\n".join(list_lines)
    )
