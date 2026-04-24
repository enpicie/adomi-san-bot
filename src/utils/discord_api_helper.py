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


def get_guild_name(guild_id: str) -> Optional[str]:
    url = f"https://discord.com/api/v10/guilds/{guild_id}"
    print(f"[discord] GET /guilds/{guild_id}")
    response = requests.get(url, headers=BOT_AUTH_HEADERS)
    if response.status_code == 200:
        print(f"[discord] -> 200")
        return response.json().get("name")
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    return None


class EventAlreadyActiveError(Exception):
    """Raised when Discord rejects a start_time update because the event is already active."""
    pass

def add_role_to_user(guild_id: str, user_id: str, role_id: str) -> RoleAssignmentResult:
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    print(f"[discord] PUT /guilds/{guild_id}/members/{user_id}/roles/{role_id}")
    response = requests.put(url, headers=BOT_AUTH_HEADERS)
    if response.status_code == 204:
        print(f"[discord] -> 204")
        return RoleAssignmentResult.OK
    if response.status_code == 403:
        print(f"[discord] ERROR -> 403 Forbidden | bot lacks permission to assign role={role_id} to user={user_id}")
        return RoleAssignmentResult.FORBIDDEN
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    return RoleAssignmentResult.ERROR

@dataclass
class ScheduledEventParams:
    name: str
    location: str
    scheduled_start_time: str  # UTC ISO 8601, e.g. "2026-03-19T19:30:00Z"
    scheduled_end_time: str    # UTC ISO 8601; required for EXTERNAL events
    description: Optional[str] = None


def create_scheduled_event(guild_id: str, params: ScheduledEventParams) -> Optional[str]:
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

    print(f"[discord] POST /guilds/{guild_id}/scheduled-events | name={params.name!r} start={params.scheduled_start_time}")
    response = requests.post(url, headers=BOT_AUTH_HEADERS, json=body)
    if response.status_code == 200:
        event_id = response.json()["id"]
        print(f"[discord] -> 200 | event_id={event_id}")
        return event_id
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    raise ValueError(_extract_discord_error(response))


def update_scheduled_event(guild_id: str, event_id: str, params: ScheduledEventParams, skip_start_time: bool = False) -> bool:
    """
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

    print(f"[discord] PATCH /guilds/{guild_id}/scheduled-events/{event_id} | name={params.name!r} skip_start_time={skip_start_time}")
    response = requests.patch(url, headers=BOT_AUTH_HEADERS, json=body)
    if response.status_code == 200:
        print(f"[discord] -> 200")
        return True

    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
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


def get_channel_message(channel_id: str, message_id: str) -> Optional[str]:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    print(f"[discord] GET /channels/{channel_id}/messages/{message_id}")
    response = requests.get(url, headers=BOT_AUTH_HEADERS)
    if response.status_code == 200:
        print(f"[discord] -> 200")
        return response.json().get("content")
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    return None


def send_channel_message(channel_id: str, content: str) -> Optional[str]:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    print(f"[discord] POST /channels/{channel_id}/messages")
    response = requests.post(url, headers=BOT_AUTH_HEADERS, json={"content": content, "flags": 4})
    if response.status_code in (200, 201):
        message_id = response.json()["id"]
        print(f"[discord] -> {response.status_code} | message_id={message_id}")
        return message_id
    print(f"[discord] ERROR -> {response.status_code} | channel_id={channel_id} | {_extract_discord_error(response)}")
    return None


def edit_channel_message(channel_id: str, message_id: str, content: str) -> bool:
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    print(f"[discord] PATCH /channels/{channel_id}/messages/{message_id}")
    response = requests.patch(url, headers=BOT_AUTH_HEADERS, json={"content": content, "flags": 4})
    if response.status_code == 200:
        print(f"[discord] -> 200")
        return True
    print(f"[discord] ERROR -> {response.status_code} | channel_id={channel_id} message_id={message_id} | {_extract_discord_error(response)}")
    return False


def delete_scheduled_event(guild_id: str, event_id: str) -> bool:
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"
    print(f"[discord] DELETE /guilds/{guild_id}/scheduled-events/{event_id}")
    response = requests.delete(url, headers=BOT_AUTH_HEADERS)
    if response.status_code == 204:
        print(f"[discord] -> 204")
        return True
    if response.status_code == 404:
        print(f"[discord] ERROR -> 404 Not Found | event_id={event_id} does not exist on Discord (manually deleted from server?)")
        return False
    if response.status_code == 403:
        print(f"[discord] ERROR -> 403 Forbidden | bot lacks permission to delete events in guild={guild_id}")
        return False
    print(f"[discord] ERROR -> {response.status_code} | {_extract_discord_error(response)}")
    return False
