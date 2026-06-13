import re
import boto3
import requests

import constants
import commands.event.startgg.startgg_graphql as startgg_graphql
from commands.event.startgg.models.startgg_event import StartggEvent

STARTGG_API_URL = "https://api.start.gg/gql/alpha"

_SET_STATE_COMPLETED = 3


class StartggAuthError(Exception):
    """Raised when start.gg rejects a request due to invalid or expired OAuth token."""

class StartggPermissionError(Exception):
    """Raised when start.gg rejects a report request due to insufficient permissions on the connected account."""

_startgg_api_token: str | None = None

_secretsmanager_client = None

def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
    return _secretsmanager_client

def _get_startgg_api_token() -> str:
    global _startgg_api_token
    if _startgg_api_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=constants.STARTGG_SECRET_NAME)
        _startgg_api_token = response["SecretString"]
    return _startgg_api_token

_STARTGG_SLUG_PATTERN = re.compile(r"tournament/[^/]+/event/[^/]+")

def extract_startgg_slug(startgg_link: str) -> str | None:
    """Extracts 'tournament/<t>/event/<e>' from a start.gg URL, or None if not found."""
    match = _STARTGG_SLUG_PATTERN.search(startgg_link)
    return match.group(0) if match else None

def is_valid_startgg_url(startgg_link: str) -> bool:
    return extract_startgg_slug(startgg_link) is not None

def _post_graphql(variables: dict, query: str, headers: dict) -> requests.Response:
    """Executes a start.gg GraphQL request and returns the response."""
    print(f"[startgg] POST {STARTGG_API_URL} | variables: {variables}")
    response = requests.post(
        url=STARTGG_API_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=10
    )
    print(f"[startgg] Response status: {response.status_code} | body length: {len(response.text)}")
    return response

# Hard safety cap on entrant pagination: 20 pages * 75 perPage = 1500 entrants.
_MAX_ENTRANT_PAGES = 20

def query_startgg_event(tourney_url: str) -> StartggEvent:
    """
    Executes the start.gg GraphQL query and returns a populated StartggEvent object.
    Pages through entrants (75 per page) until all entrants are fetched.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    slug = extract_startgg_slug(tourney_url)

    event_data = None
    all_nodes = []
    page = 1

    while True:
        variables = {"slug": slug, "page": page}

        response = _post_graphql(variables, startgg_graphql.EVENT_PARTICIPANTS_QUERY, headers)

        if not response.ok:
            print(f"[startgg] Error querying event: status {response.status_code}, body: {response.text[:2000]}")
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            print(f"[startgg] GraphQL errors for slug '{tourney_url}': {data['errors']}")

        page_event = data["data"]["event"]
        if event_data is None:
            event_data = page_event

        nodes = ((page_event or {}).get("entrants") or {}).get("nodes") or []
        all_nodes.extend(nodes)

        total = ((event_data or {}).get("entrants") or {}).get("pageInfo", {}).get("total") or 0

        if len(all_nodes) >= total or not nodes:
            break

        if page >= _MAX_ENTRANT_PAGES:
            print(
                f"[startgg] WARNING: entrant pagination cap of {_MAX_ENTRANT_PAGES} pages reached for "
                f"slug '{tourney_url}'; truncating at {len(all_nodes)} of {total} entrants"
            )
            break

        page += 1

    if event_data is not None and event_data.get("entrants") is not None:
        event_data["entrants"]["nodes"] = all_nodes

    return StartggEvent.from_dict(event_data)

def find_set_between_players(
    event_slug: str, player_ids: list[str]
) -> tuple[str, dict[str, str], bool] | None:
    """
    Finds a set on start.gg between the given entrant IDs.
    Returns (set_id, {entrant_id: entrant_id}, is_completed), or None if no set found.
    is_completed is True when the set state is COMPLETED (3) — score already reported.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    variables = {"eventSlug": event_slug, "entrantIds": player_ids}

    response = _post_graphql(variables, startgg_graphql.FIND_SET_QUERY, headers)

    if not response.ok:
        print(f"[startgg] Error querying sets: status {response.status_code}, body: {response.text[:2000]}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"[startgg] GraphQL errors for slug '{event_slug}': {data['errors']}")

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
    is_completed = latest.get("state") == _SET_STATE_COMPLETED
    return str(latest["id"]), {eid: eid for eid in player_ids}, is_completed

def report_set(set_id: str, winner_entrant_id: str, game_data: list[dict], oauth_token: str, is_dq: bool = False) -> None:
    """
    Reports a set result on start.gg using the server's OAuth token.
    game_data: list of {"winnerId": entrant_id, "gameNum": int}
    Raises StartggAuthError if the token is invalid or expired.
    """
    headers = {"Authorization": f"Bearer {oauth_token}"}
    variables = {"setId": set_id, "winnerId": winner_entrant_id, "isDQ": is_dq, "gameData": game_data}

    response = _post_graphql(variables, startgg_graphql.REPORT_SET_MUTATION, headers)

    if response.status_code == 401:
        raise StartggAuthError("start.gg OAuth token is invalid or expired.")

    if not response.ok:
        print(f"[startgg] Error reporting set: status {response.status_code}, body: {response.text[:2000]}")
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        print(f"[startgg] GraphQL errors reporting set '{set_id}': {data['errors']}")
        if any("permission" in (e.get("message") or "").lower() for e in data["errors"]):
            raise StartggPermissionError()
        raise ValueError("start.gg returned an error while reporting the set. Please check that the set is still open or contact an organizer.")
