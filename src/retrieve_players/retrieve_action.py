import re
from discord import Message
from retrieve_players.retrieve import get_key, get_tourney, get_players, output_list

# Only validates up until the event name
# Example:
# Valid: https://www.start.gg/tournament/midweek-melting-27/event/mbaacc-double-elim
# Invalid: https://www.start.gg/tournament/midweek-melting-27/event/mbaacc-double-elim/overview
def validate_link(startgg_link: str) -> bool:
    startgg_pattern = re.compile(r"^https:\/\/www.start.gg\/tournament\/([^\/]+)\/event\/([^\/]+)$")
    return re.fullmatch(startgg_pattern, startgg_link)

# Function that the command mapping will call.
def retrieve_player_list(startgg_link: str) -> Message:
    if validate_link(startgg_link):
        node = get_key(startgg_link)
        tourney_name = get_tourney(node)
        players = get_players(node)
        return Message(content=output_list(tourney_name, players))
    else:
        return Message(content="Invalid start.gg link!")