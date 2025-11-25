import re
from commands.models.response_message import ResponseMessage
from commands.get_participants.startgg.startgg_api import get_event, get_tourney_name, get_participants, participants_to_string

def validate_startgg_link(startgg_link: str) -> bool:
    startgg_pattern = re.compile(r"^https:\/\/www.start.gg\/tournament\/([^\/]+)\/event\/([^\/]+)$")

    return bool(re.fullmatch(startgg_pattern, startgg_link))

def get_startgg_participants_msg(startgg_link: str) -> ResponseMessage:
    if validate_startgg_link(startgg_link):
        event_dict = get_event(startgg_link)
        tourney_name = get_tourney_name(event_dict)
        participants = get_participants(event_dict)
        return ResponseMessage(content=participants_to_string(tourney_name, participants))
    else:
        return ResponseMessage(content="Invalid start.gg link!")
