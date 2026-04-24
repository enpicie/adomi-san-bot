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
    """Send a message to a Discord channel.

    Returns True on success, None on 403 Forbidden (missing permissions), False on other failure.
    """
    resp = _request("POST", f"{_DISCORD_API}/channels/{channel_id}/messages", json={"content": content, "flags": 4})
    if resp.status_code in (200, 201):
        return True
    if resp.status_code == 403:
        logger.error(f"Missing permissions to send message to channel {channel_id}: {resp.status_code} {resp.text}")
        return None
    logger.error(f"Failed to send message to channel {channel_id}: {resp.status_code} {resp.text}")
    return False


def send_organizer_notification(notification_channel_id, message, organizer_role=None, ping_organizers=False):
    """Send a notification message to the organizer notification channel.

    Pings the organizer role if ping_organizers is True and organizer_role is set.
    Does not recurse — if this send fails, the error is only logged.
    """
    if ping_organizers and organizer_role:
        message = f"<@&{organizer_role}> {message}"
    resp = _request("POST", f"{_DISCORD_API}/channels/{notification_channel_id}/messages", json={"content": message, "flags": 4})
    if resp.status_code not in (200, 201):
        logger.error(
            f"Failed to send organizer notification to channel {notification_channel_id}: {resp.status_code} {resp.text}"
        )


def send_permission_error_notification(notification_channel_id, failed_channel_id, organizer_role=None, ping_organizers=False):
    """Notify organizers that Adomin lacks permissions to send to a channel."""
    send_organizer_notification(
        notification_channel_id,
        f"⚠️ Adomin is missing permission to send messages in <#{failed_channel_id}>. "
        "Please check that Adomin has the **Send Messages** and **View Channel** permissions there.",
        organizer_role=organizer_role,
        ping_organizers=ping_organizers,
    )


def get_channel_message(channel_id, message_id):
    """Fetch the content of an existing channel message. Returns content string or None on failure."""
    resp = _request("GET", f"{_DISCORD_API}/channels/{channel_id}/messages/{message_id}")
    if resp.status_code == 200:
        return resp.json().get("content")
    logger.error(
        f"Failed to fetch message {message_id} in channel {channel_id}: {resp.status_code} {resp.text}"
    )
    return None


def edit_channel_message(channel_id, message_id, content):
    """Edit an existing message in a Discord channel.

    Returns True on success, None on 403 Forbidden (missing permissions), False on other failure.
    """
    resp = _request("PATCH", f"{_DISCORD_API}/channels/{channel_id}/messages/{message_id}", json={"content": content, "flags": 4})
    if resp.status_code == 200:
        return True
    if resp.status_code == 403:
        logger.error(f"Missing permissions to edit message {message_id} in channel {channel_id}: {resp.status_code} {resp.text}")
        return None
    logger.error(f"Failed to edit message {message_id} in channel {channel_id}: {resp.status_code} {resp.text}")
    return False


def delete_guild_event(guild_id, event_id):
    """Delete a scheduled event from Discord. Returns True on success or if already gone (404)."""
    resp = _request("DELETE", f"{_DISCORD_API}/guilds/{guild_id}/scheduled-events/{event_id}")
    if resp.status_code in (200, 204):
        return True
    if resp.status_code == 404:
        logger.warning(f"Discord event {event_id} for guild {guild_id} already gone (404) — treating as success")
        return True
    logger.error(
        f"Failed to delete Discord event {event_id} for guild {guild_id}: "
        f"{resp.status_code} {resp.text}"
    )
    return False
