from dataclasses import dataclass
from typing import Optional

import requests
import constants

BOT_AUTH_HEADERS = {
    "Authorization": f"Bot {constants.DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}

def add_role_to_user(guild_id: str, user_id: str, role_id: str) -> bool:
    """
    Adds a role to a Discord guild member using the Discord REST API.
    :return: True if successful (204 response), False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    response = requests.put(url, headers=BOT_AUTH_HEADERS)

    if response.status_code == 204:
        return True
    print(f"Error adding role: status {response.status_code}, body: {response.text}")
    return False

@dataclass
class ScheduledEventParams:
    name: str
    location: str
    scheduled_start_time: str  # UTC ISO 8601, e.g. "2026-03-19T19:30:00Z"
    scheduled_end_time: str    # UTC ISO 8601; required for EXTERNAL events
    description: Optional[str] = None

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

    response = requests.post(url, headers=BOT_AUTH_HEADERS, json=body)

    if response.status_code == 200:
        return response.json()["id"]
    print(f"Error creating scheduled event: status {response.status_code}, body: {response.text}")
    return None


def delete_scheduled_event(guild_id: str, event_id: str) -> bool:
    """
    Deletes a Discord guild scheduled event.
    :return: True if successful (204 response), False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"
    response = requests.delete(url, headers=BOT_AUTH_HEADERS)

    if response.status_code == 204:
        return True
    print(f"Error deleting scheduled event: status {response.status_code}, body: {response.text}")
    return False
