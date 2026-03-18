import re
import boto3
import requests

import constants
import commands.event.startgg.startgg_graphql as startgg_graphql
from commands.event.startgg.models.startgg_event import StartggEvent

STARTGG_API_URL = "https://api.start.gg/gql/alpha"

_startgg_api_token: str | None = None

def _get_startgg_api_token() -> str:
    global _startgg_api_token
    if _startgg_api_token is None:
        client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
        response = client.get_secret_value(SecretId=constants.STARTGG_SECRET_NAME)
        _startgg_api_token = response["SecretString"]
    return _startgg_api_token

_STARTGG_SLUG_PATTERN = re.compile(r"tournament/[^/]+/event/[^/]+")

def extract_startgg_slug(startgg_link: str) -> str | None:
    """Extracts 'tournament/<t>/event/<e>' from a start.gg URL, or None if not found."""
    match = _STARTGG_SLUG_PATTERN.search(startgg_link)
    return match.group(0) if match else None

def is_valid_startgg_url(startgg_link: str) -> bool:
    return extract_startgg_slug(startgg_link) is not None

def query_startgg_event(tourney_url: str) -> StartggEvent:
    """
    Executes the start.gg GraphQL query and returns a populated StartggEvent object.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    request_body = {
        "query": startgg_graphql.EVENT_PARTICIPANTS_QUERY,
        "variables": {
            "slug": extract_startgg_slug(tourney_url)
        }
    }

    response = requests.post(
        url=STARTGG_API_URL,
        json=request_body,
        headers=headers,
        timeout=10
    )

    if not response.ok:
        print(f"Error querying start.gg: status {response.status_code}, body: {response.text}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"start.gg GraphQL errors for slug '{tourney_url}': {data['errors']}")

    return StartggEvent.from_dict(data["data"]["event"])

def find_set_between_players(event_slug: str, player_ids: list[str]) -> tuple[str, dict[str, str]] | None:
    """
    Finds a pending set on start.gg between two participants (by participant ID).
    Returns (set_id, {participant_id: entrant_id}) for both players, or None if no set found.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    request_body = {
        "query": startgg_graphql.FIND_SET_QUERY,
        "variables": {
            "eventSlug": event_slug,
            "entrantIds": player_ids
        }
    }

    response = requests.post(
        url=STARTGG_API_URL,
        json=request_body,
        headers=headers,
        timeout=10
    )

    if not response.ok:
        print(f"Error querying start.gg sets: status {response.status_code}, body: {response.text}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"start.gg GraphQL errors for slug '{event_slug}': {data['errors']}")

    entrant_id_set = set(player_ids)
    sets = data["data"]["event"]["sets"]["nodes"]

    matching_sets = []
    for set_node in sets:
        slot_entrant_ids = set()
        for slot in set_node["slots"]:
            entrant = slot.get("entrant")
            if entrant is None:
                continue
            slot_entrant_ids.add(str(entrant["id"]))

        if entrant_id_set.issubset(slot_entrant_ids):
            matching_sets.append(set_node)

    if not matching_sets:
        return None

    latest = max(matching_sets, key=lambda s: s.get("createdAt") or 0)
    return str(latest["id"]), {eid: eid for eid in player_ids}

def report_set(set_id: str, winner_entrant_id: str, game_data: list[dict]) -> None:
    """
    Reports a set result on start.gg.
    game_data: list of {"winnerId": entrant_id, "gameNum": int}
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    request_body = {
        "query": startgg_graphql.REPORT_SET_MUTATION,
        "variables": {
            "setId": set_id,
            "winnerId": winner_entrant_id,
            "gameData": game_data
        }
    }

    response = requests.post(
        url=STARTGG_API_URL,
        json=request_body,
        headers=headers,
        timeout=10
    )

    if not response.ok:
        print(f"Error reporting set on start.gg: status {response.status_code}, body: {response.text}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"start.gg GraphQL errors reporting set '{set_id}': {data['errors']}")
        raise ValueError(f"start.gg returned an error while reporting the set. Please check that the set is still open.")
