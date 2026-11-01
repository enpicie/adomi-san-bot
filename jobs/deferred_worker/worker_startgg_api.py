# MIRROR: src/commands/event/startgg/startgg_api.py + startgg_graphql.py +
# models/startgg_event.py — keep in sync (independent Lambda packaging prevents imports).
#
# Returns plain dicts rather than the dataclasses src uses, but the participant
# shape written to DynamoDB must stay byte-identical to
# RegisteredParticipant.to_dict() / Participant.to_dict().
#
# Deliberate divergence: an unknown slug (start.gg returns event: null) parses
# here as an empty event, so the caller reports "Could not retrieve the start
# time"; src's StartggEvent.from_dict raises AttributeError on None instead.
import logging
import re
from datetime import datetime, timezone as dt_timezone

import boto3
import requests

import worker_constants as constants

logger = logging.getLogger()

STARTGG_API_URL = "https://api.start.gg/gql/alpha"
STARTGG_SOURCE = "startgg"
NO_DISCORD_ID_PLACEHOLDER = "no_id"

# Hard safety cap on entrant pagination: 20 pages * 75 perPage = 1500 entrants.
_MAX_ENTRANT_PAGES = 20

_STARTGG_SLUG_PATTERN = re.compile(r"tournament/[^/]+/event/[^/]+")

# MIRROR: src/commands/event/startgg/startgg_api.py STARTGG_UNAVAILABLE_MESSAGE
STARTGG_UNAVAILABLE_MESSAGE = "😔 I couldn't get a response from start.gg. Please try again in a few minutes."


class StartggUnavailableError(Exception):
    """start.gg could not be reached or answered with an HTTP error. The message is shown to the user as-is."""

EVENT_PARTICIPANTS_QUERY = """
    query EventEntrants($slug: String, $page: Int!) {
        event(slug: $slug) {
            id
            name
            startAt
            tournament {
                name
                venueAddress
                venueName
            }
            entrants(query: {
                page: $page
                perPage: 75
            }) {
                pageInfo {
                    total
                }
                nodes {
                    id
                    participants {
                        id
                        gamerTag
                        user {
                            authorizations(types: DISCORD) {
                                externalId
                                externalUsername
                            }
                        }
                    }
                }
            }
        }
    }
"""

_startgg_api_token = None
_secretsmanager_client = None


def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager", region_name=constants.AWS_REGION)
    return _secretsmanager_client


def _get_startgg_api_token() -> str:
    """Fetches and caches the start.gg API token from Secrets Manager (once per cold start)."""
    global _startgg_api_token
    if _startgg_api_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=constants.STARTGG_SECRET_NAME)
        _startgg_api_token = response["SecretString"]
    return _startgg_api_token


def extract_startgg_slug(startgg_link: str) -> str | None:
    """Extracts 'tournament/<t>/event/<e>' from a start.gg URL, or None if not found."""
    if not startgg_link:
        return None
    match = _STARTGG_SLUG_PATTERN.search(startgg_link)
    return match.group(0) if match else None


def is_valid_startgg_url(startgg_link: str) -> bool:
    return extract_startgg_slug(startgg_link) is not None


def _unix_to_utc_iso(unix_ts) -> str | None:
    if unix_ts is None:
        return None
    return datetime.fromtimestamp(unix_ts, tz=dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return datetime.now(dt_timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _post_graphql(variables: dict, query: str, headers: dict) -> requests.Response:
    """Executes a start.gg GraphQL request and returns the response."""
    logger.info(f"[startgg] POST {STARTGG_API_URL} | variables: {variables}")
    response = requests.post(
        url=STARTGG_API_URL,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=10,
    )
    logger.info(f"[startgg] Response status: {response.status_code} | body length: {len(response.text)}")
    return response


def _parse_participants(event_data: dict) -> tuple[list, list]:
    """Split entrants into those with a linked Discord account and those without."""
    registered = []
    no_discord = []

    for entrant in ((event_data or {}).get("entrants") or {}).get("nodes") or []:
        participant_data = (entrant.get("participants") or [None])[0]
        if participant_data is None:
            continue

        startgg_name = participant_data.get("gamerTag")
        user = participant_data.get("user")
        authorizations = user.get("authorizations") if user else []

        if authorizations:
            registered.append({
                "display_name": startgg_name,
                "user_id": authorizations[0].get("externalId"),
                "time_added": _now_iso(),
                "source": STARTGG_SOURCE,
                "external_id": str(entrant.get("id")),
            })
        else:
            no_discord.append({
                "display_name": startgg_name,
                "user_id": NO_DISCORD_ID_PLACEHOLDER,
                "time_added": _now_iso(),
            })

    return registered, no_discord


def query_startgg_event(tourney_url: str) -> dict:
    """Query a start.gg event, paging through entrants (75 per page).

    :return: dict with event_name, start_time_utc, location, participants and
             no_discord_participants. Participants are already in the shape
             DynamoDB stores.
    """
    headers = {"Authorization": f"Bearer {_get_startgg_api_token()}"}
    slug = extract_startgg_slug(tourney_url)

    event_data = None
    all_nodes = []
    page = 1

    while True:
        try:
            response = _post_graphql({"slug": slug, "page": page}, EVENT_PARTICIPANTS_QUERY, headers)
            if not response.ok:
                logger.error(f"[startgg] Error querying event: status {response.status_code}")
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[startgg] Request failed querying event slug {slug!r}: {type(e).__name__}")
            raise StartggUnavailableError(STARTGG_UNAVAILABLE_MESSAGE) from e

        data = response.json()
        if "errors" in data:
            logger.error(f"[startgg] GraphQL errors for slug {slug!r}: {data['errors']}")

        page_event = data["data"]["event"]
        if event_data is None:
            event_data = page_event

        nodes = ((page_event or {}).get("entrants") or {}).get("nodes") or []
        all_nodes.extend(nodes)

        total = ((event_data or {}).get("entrants") or {}).get("pageInfo", {}).get("total") or 0

        if len(all_nodes) >= total or not nodes:
            break

        if page >= _MAX_ENTRANT_PAGES:
            logger.warning(
                f"[startgg] entrant pagination cap of {_MAX_ENTRANT_PAGES} pages reached for "
                f"slug {slug!r}; truncating at {len(all_nodes)} of {total} entrants"
            )
            break

        page += 1

    if event_data is not None and event_data.get("entrants") is not None:
        event_data["entrants"]["nodes"] = all_nodes

    event_data = event_data or {}
    tournament = event_data.get("tournament") or {}
    tourney_name = tournament.get("name", "Unknown Tournament")
    registered, no_discord = _parse_participants(event_data)

    return {
        "event_name": event_data.get("name", tourney_name),
        "start_time_utc": _unix_to_utc_iso(event_data.get("startAt")),
        "location": tournament.get("venueName") or tournament.get("venueAddress") or "Online",
        "participants": registered,
        "no_discord_participants": no_discord,
    }
