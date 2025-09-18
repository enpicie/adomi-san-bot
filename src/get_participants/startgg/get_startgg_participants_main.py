import re
from commands.models.response_message import ResponseMessage
from get_participants.startgg.get_startgg_participants import get_event, get_tourney, get_participants, output_list

# Only validates up until the event name
# Example:
# Valid: https://www.start.gg/tournament/midweek-melting-27/event/mbaacc-double-elim
# Invalid: https://www.start.gg/tournament/midweek-melting-27/event/mbaacc-double-elim/overview
def validate_startgg_link(startgg_link: str) -> bool:
    startgg_pattern = re.compile(r"^https:\/\/www.start.gg\/tournament\/([^\/]+)\/event\/([^\/]+)$")
    return re.fullmatch(startgg_pattern, startgg_link)

# This function takes a start.gg link as an input
# Returns a list of participants as a string to then be sent as a response message
def get_startgg_participants_list(startgg_link: str) -> ResponseMessage:
    if validate_startgg_link(startgg_link):
        event_dict = get_event(startgg_link)
        tourney_name = get_tourney(event_dict)
        participants = get_participants(event_dict)
        return ResponseMessage(content=output_list(tourney_name, participants))
    else:
        return ResponseMessage(content="Invalid start.gg link!")