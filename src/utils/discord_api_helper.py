from dataclasses import dataclass
from typing import Optional

from enum import Enum

import requests
import constants


class RoleAssignmentResult(Enum):
    OK = "ok"
    FORBIDDEN = "forbidden"
    ERROR = "error"

BOT_AUTH_HEADERS = {
    "Authorization": f"Bot {constants.DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}

_START_TIME_LOCKED_CODE = "GUILD_SCHEDULED_EVENT_SCHEDULE_INVALID_START_BY_STATUS"


class EventAlreadyActiveError(Exception):
    """Raised when Discord rejects a start_time update because the event is already active."""
    pass

def add_role_to_user(guild_id: str, user_id: str, role_id: str) -> RoleAssignmentResult:
    """
    Adds a role to a Discord guild member using the Discord REST API.
    :return: RoleAssignmentResult.OK on success, .FORBIDDEN on 403, .ERROR otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    print(f"[discord] PUT {url}")
    response = requests.put(url, headers=BOT_AUTH_HEADERS)
    print(f"[discord] Response status: {response.status_code} | body: {response.text}")

    if response.status_code == 204:
        return RoleAssignmentResult.OK
    if response.status_code == 403:
        return RoleAssignmentResult.FORBIDDEN
    print(f"[discord] Error adding role: status {response.status_code}, body: {response.text}")
    return RoleAssignmentResult.ERROR

@dataclass
class ScheduledEventParams:
    name: str
    location: str
    scheduled_start_time: str  # UTC ISO 8601, e.g. "2026-03-19T19:30:00Z"
    scheduled_end_time: str    # UTC ISO 8601; required for EXTERNAL events
    description: Optional[str] = None

def _extract_discord_error(response: requests.Response) -> str:
    try:
        body = response.json()
        for field_errors in body.get("errors", {}).values():
            for err in field_errors.get("_errors", []):
                if "message" in err:
                    return err["message"]
        return body.get("message", "Unknown Discord API error")
    except Exception:
        return f"HTTP {response.status_code}"


def create_scheduled_event(guild_id: str, params: ScheduledEventParams) -> Optional[str]:
    """
    Creates a Discord guild scheduled event (EXTERNAL type).
    :return: The created event ID if successful, None otherwise
    """

    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events"
    body = {
        "name": params.name,
        "privacy_level": 2, # = GUILD_ONLY (only option Discord currently supports)
        "scheduled_start_time": params.scheduled_start_time,
        "scheduled_end_time": params.scheduled_end_time,
        "entity_type": 3, # = EXTERNAL (location-based, no Discord channel required)
        "entity_metadata": { "location": params.location },
    }
    if params.description:
        body["description"] = params.description

    print(f"[discord] POST {url} | body: {body}")
    response = requests.post(url, headers=BOT_AUTH_HEADERS, json=body)
    print(f"[discord] Response status: {response.status_code} | body: {response.text}")

    if response.status_code == 200:
        return response.json()["id"]
    print(f"[discord] Error creating scheduled event: status {response.status_code}, body: {response.text}")
    raise ValueError(_extract_discord_error(response))


def update_scheduled_event(guild_id: str, event_id: str, params: ScheduledEventParams, skip_start_time: bool = False) -> bool:
    """
    Updates a Discord guild scheduled event (EXTERNAL type).
    :param skip_start_time: If True, omits scheduled_start_time from the request body.
    :return: True if successful (200 response), False otherwise
    :raises EventAlreadyActiveError: if Discord rejects the start time update because the event is active.
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"
    body = {
        "name": params.name,
        "scheduled_end_time": params.scheduled_end_time,
        "entity_metadata": {"location": params.location},
    }
    if not skip_start_time:
        body["scheduled_start_time"] = params.scheduled_start_time
    if params.description:
        body["description"] = params.description

    print(f"[discord] PATCH {url} | body: {body}")
    response = requests.patch(url, headers=BOT_AUTH_HEADERS, json=body)
    print(f"[discord] Response status: {response.status_code} | body: {response.text}")

    if response.status_code == 200:
        return True

    print(f"[discord] Error updating scheduled event: status {response.status_code}, body: {response.text}")
    try:
        errors = response.json().get("errors", {})
        start_time_errors = errors.get("scheduled_start_time", {}).get("_errors", [])
        if any(e.get("code") == _START_TIME_LOCKED_CODE for e in start_time_errors):
            raise EventAlreadyActiveError("Event is already active; start time cannot be changed.")
    except EventAlreadyActiveError:
        raise
    except Exception:
        pass
    return False


def delete_scheduled_event(guild_id: str, event_id: str) -> bool:
    """
    Deletes a Discord guild scheduled event.
    :return: True if successful (204 response), False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"
    print(f"[discord] DELETE {url}")
    response = requests.delete(url, headers=BOT_AUTH_HEADERS)
    print(f"[discord] Response status: {response.status_code} | body: {response.text}")

    if response.status_code == 204:
        return True
    print(f"[discord] Error deleting scheduled event: status {response.status_code}, body: {response.text}")
    return False
