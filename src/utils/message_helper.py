from typing import List, Dict

from database.models.participant import Participant

def get_user_ping(user_id: str) -> str:
    return f"<@{user_id}>"

def get_channel_mention(channel_id: str) -> str:
    return f"<#{channel_id}>"

def get_role_ping(role_id: str) -> str:
    return f"<@&{role_id}>"

def build_participants_list(list_header: str, participants: List[Dict]) -> str:
    """
    Builds a sorted, numbered list of participants using direct attribute access.
    List passed in will be dict of Participant since it comes from DynamoDB.
    """
    if len(participants) == 0:
        return f"{list_header}\nNo participants"

    print(f"Building participants list for {participants}")

    # Sort the participants list by their display_name attribute
    sorted_participants = sorted(
        participants,
        key=lambda p: p[Participant.Keys.DISPLAY_NAME]
    )

    list_lines = []

    # Format as a numbered list (starting at 1)
    for i, p in enumerate(sorted_participants, 1):
        user_id = p[Participant.Keys.USER_ID]
        display_name = p[Participant.Keys.DISPLAY_NAME]

        if user_id == Participant.DEFAULT_ID_PLACEHOLDER:
            line = f"{i}. {display_name}"
        else:
            line = f"{i}. {get_user_ping(user_id)}: {display_name}"
        list_lines.append(line)

    return (
        f"{list_header}\n"
        + "\n".join(list_lines)
    )
