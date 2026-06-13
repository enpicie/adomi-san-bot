import json
import logging
import os
import time

import boto3
import requests

DISCORD_BOT_TOKEN_SECRET_NAME = os.environ["DISCORD_BOT_TOKEN_SECRET_NAME"]
_DISCORD_API = "https://discord.com/api/v10"

# Discord message flag: suppress link-preview embeds
# https://discord.com/developers/docs/resources/message#message-object-message-flags
_SUPPRESS_EMBEDS = 4

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_bot_token = None
_secretsmanager_client = None


def _get_secretsmanager_client():
    """Returns the shared Secrets Manager client, creating it on first use."""
    global _secretsmanager_client
    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager")
    return _secretsmanager_client


def _get_bot_token() -> str:
    """Fetches and caches the Discord bot token from Secrets Manager (once per cold start)."""
    global _bot_token
    if _bot_token is None:
        response = _get_secretsmanager_client().get_secret_value(SecretId=DISCORD_BOT_TOKEN_SECRET_NAME)
        _bot_token = response["SecretString"]
    return _bot_token


def _role_ping(role_id) -> str:
    return f"<@&{role_id}>"


def _discord_request(method, url, **kwargs):
    headers = {"Authorization": f"Bot {_get_bot_token()}"}
    while True:
        r = requests.request(method, url, headers=headers, **kwargs)
        if r.status_code != 429:
            return r
        time.sleep(r.json().get("retry_after", 1))


def _notify(notification_channel_id, message, organizer_role=None, ping_organizers=False):
    if ping_organizers and organizer_role:
        message = f"{_role_ping(organizer_role)} {message}"
    resp = _discord_request("POST", f"{_DISCORD_API}/channels/{notification_channel_id}/messages", json={"content": message, "flags": _SUPPRESS_EMBEDS})
    if resp.status_code not in (200, 201):
        logger.error(f"Failed to send notification to channel {notification_channel_id}: {resp.status_code} {resp.text}")


def handler(event, context):
    """SQS-triggered Lambda: removes a Discord role from a user per queued message,
    notifying organizers when the bot lacks permission to do so."""
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

        if resp.status_code == 404:
            logger.info(f"Skipping role removal for user {user_id} in guild {guild_id}: user or role {role_id} no longer exists (404)")
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
