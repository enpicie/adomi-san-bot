import json
import logging
import os
import time

import requests

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
_DISCORD_API = "https://discord.com/api/v10"
_HEADERS = {"Authorization": f"Bot {TOKEN}"}

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _discord_request(method, url, **kwargs):
    while True:
        r = requests.request(method, url, headers=_HEADERS, **kwargs)
        if r.status_code != 429:
            return r
        time.sleep(r.json().get("retry_after", 1))


def _notify(notification_channel_id, message, organizer_role=None, ping_organizers=False):
    if ping_organizers and organizer_role:
        message = f"<@&{organizer_role}> {message}"
    resp = _discord_request("POST", f"{_DISCORD_API}/channels/{notification_channel_id}/messages", json={"content": message, "flags": 4})
    if resp.status_code not in (200, 201):
        logger.error(f"Failed to send notification to channel {notification_channel_id}: {resp.status_code} {resp.text}")


def handler(event, context):
    for record in event["Records"]:
        payload = json.loads(record["body"])

        guild_id = payload["guild_id"]
        user_id  = payload["user_id"]
        role_id  = payload["role_id"]
        notification_channel_id = payload.get("notification_channel_id")
        organizer_role = payload.get("organizer_role")
        ping_organizers = payload.get("ping_organizers", False)

        url = f"{_DISCORD_API}/guilds/{guild_id}/members/{user_id}/roles/{role_id}"

        resp = _discord_request("DELETE", url)
        if resp.status_code in (204, 200):
            continue

        if resp.status_code == 403:
            logger.error(f"Missing permissions to remove role {role_id} from user {user_id} in guild {guild_id}: {resp.text}")
            if notification_channel_id:
                _notify(
                    notification_channel_id,
                    f"⚠️ Adomin is missing permission to remove the participant role from <@{user_id}>. "
                    "Please check that Adomin's role is above the participant role in the server role list.",
                    organizer_role=organizer_role,
                    ping_organizers=ping_organizers,
                )
        else:
            raise Exception(f"Failed to remove role {role_id} from user {user_id}: {resp.status_code} {resp.text}")
