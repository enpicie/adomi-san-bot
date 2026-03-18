import logging
import os
import time

import requests

logger = logging.getLogger()

_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
_DISCORD_API = "https://discord.com/api/v10"


def _request(method, url, json=None):
    while True:
        r = requests.request(method, url, headers={"Authorization": f"Bot {_TOKEN}"}, json=json)
        if r.status_code != 429:
            return r
        retry_after = r.json().get("retry_after", 1)
        logger.warning(f"Rate limited on {method} {url}, retrying after {retry_after}s")
        time.sleep(retry_after)


def get_guild_events(guild_id):
    """Fetch all scheduled events for a guild. Returns list or None on failure."""
    resp = _request("GET", f"{_DISCORD_API}/guilds/{guild_id}/scheduled-events")
    if resp.status_code != 200:
        logger.error(
            f"Failed to fetch Discord events for guild {guild_id}: {resp.status_code} {resp.text}"
        )
        return None
    return resp.json()


def send_channel_message(channel_id, content):
    """Send a message to a Discord channel. Returns True on success."""
    resp = _request("POST", f"{_DISCORD_API}/channels/{channel_id}/messages", json={"content": content})
    if resp.status_code not in (200, 201):
        logger.error(
            f"Failed to send message to channel {channel_id}: {resp.status_code} {resp.text}"
        )
        return False
    return True


def delete_guild_event(guild_id, event_id):
    """Delete a scheduled event from Discord. Returns True on success."""
    resp = _request("DELETE", f"{_DISCORD_API}/guilds/{guild_id}/scheduled-events/{event_id}")
    if resp.status_code not in (200, 204):
        logger.error(
            f"Failed to delete Discord event {event_id} for guild {guild_id}: "
            f"{resp.status_code} {resp.text}"
        )
        return False
    return True
