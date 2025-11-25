import re
import requests

import constants
import commands.get_registered.startgg.startgg_graphql as startgg_graphql
from commands.get_registered.startgg.models.startgg_event import StartggEvent

STARTGG_API_URL = "https://api.start.gg/gql/alpha"

def is_valid_startgg_url(startgg_link: str) -> bool:
    startgg_pattern = re.compile(r"^https:\/\/www.start.gg\/tournament\/([^\/]+)\/event\/([^\/]+)$")

    return bool(re.fullmatch(startgg_pattern, startgg_link))

def query_startgg_event(tourney_url: str) -> StartggEvent:
    """
    Executes the start.gg GraphQL query and returns a populated StartggEvent object.
    """

    headers = { "Authorization": f"Bearer {constants.STARTGG_API_TOKEN}" }
    request_body = {
        "query": startgg_graphql.EVENT_PARTICIPANTS_QUERY,
        "variables": {
            "slug": tourney_url.removeprefix("https://www.start.gg/")
        }
    }

    response = requests.post(
        url=STARTGG_API_URL,
        json=request_body,
        headers=headers,
        timeout=10 # Add a timeout for safety
    )
    response.raise_for_status()

    return StartggEvent.from_dict(response.json()["data"]["event"])
