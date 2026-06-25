# MIRROR: src/commands/event/startgg/startgg_api.py + startgg_graphql.py — keep in sync
# (independent Lambda packaging prevents importing from src/). This is a *minimal* mirror: it only
# fetches an event's scheduled start time (startAt). The src copy additionally pages entrants and
# parses participants; the scheduled job's reschedule scout does not need those, so they are
# intentionally omitted here. The slug regex, API URL, and unix→ISO formatting must stay identical.
import logging
import re
from datetime import datetime, timezone

import requests

import scheduled_job_constants as constants

logger = logging.getLogger()

_STARTGG_API_URL = "https://api.start.gg/gql/alpha"
_REQUEST_TIMEOUT_SECONDS = 10

# MIRROR: _STARTGG_SLUG_PATTERN in src startgg_api.py
_STARTGG_SLUG_PATTERN = re.compile(r"tournament/[^/]+/event/[^/]+")

# MIRROR: a startAt-only subset of EVENT_PARTICIPANTS_QUERY in src startgg_graphql.py
_EVENT_START_TIME_QUERY = """
    query EventStartTime($slug: String) {
        event(slug: $slug) {
            id
            startAt
        }
    }
"""


def extract_startgg_slug(startgg_url):
    """Extracts 'tournament/<t>/event/<e>' from a start.gg URL, or None if not found."""
    match = _STARTGG_SLUG_PATTERN.search(startgg_url or "")
    return match.group(0) if match else None


def get_event_start_time_utc(startgg_url):
    """Query start.gg for an event's scheduled start time.

    Returns the start time as a UTC ISO 8601 string (e.g. '2026-03-19T19:30:00Z'), or None if the
    URL is invalid, the event has no start time, or the request fails. Best-effort: all failures
    are logged and swallowed so a start.gg outage never breaks the rest of the poller run.
    """
    slug = extract_startgg_slug(startgg_url)
    if not slug:
        logger.warning(f"Could not extract start.gg slug from URL '{startgg_url}'")
        return None

    try:
        response = requests.post(
            _STARTGG_API_URL,
            json={"query": _EVENT_START_TIME_QUERY, "variables": {"slug": slug}},
            headers={"Authorization": f"Bearer {constants.get_startgg_api_token()}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        logger.error(f"start.gg request failed for slug '{slug}': {e}")
        return None

    if not response.ok:
        logger.error(f"start.gg returned {response.status_code} for slug '{slug}'")
        return None

    try:
        data = response.json()
    except ValueError as e:
        logger.error(f"start.gg returned non-JSON for slug '{slug}': {e}")
        return None

    if data.get("errors"):
        logger.error(f"start.gg GraphQL errors for slug '{slug}': {data['errors']}")

    event = (data.get("data") or {}).get("event")
    if not event:
        return None
    return _unix_to_utc_iso(event.get("startAt"))


def _unix_to_utc_iso(unix_ts):
    """MIRROR: _unix_to_utc_iso in src startgg_event.py — keep format identical."""
    if unix_ts is None:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
