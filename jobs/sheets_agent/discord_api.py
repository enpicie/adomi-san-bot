import json
import time

import requests

import constants

DISCORD_API_BASE = "https://discord.com/api/v10"

_BOT_AUTH_HEADERS = {
    "Authorization": f"Bot {constants.DISCORD_BOT_TOKEN}",
    "Content-Type": "application/json",
}


def discord_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a Discord API request with automatic 429 retry."""
    response = requests.request(method, url, headers=_BOT_AUTH_HEADERS, timeout=10, **kwargs)
    if response.status_code == 429:
        retry_after = response.json().get("retry_after", 1.0)
        print(f"[discord] rate limited on {method} {url}, sleeping {retry_after}s")
        time.sleep(retry_after)
        response = requests.request(method, url, headers=_BOT_AUTH_HEADERS, timeout=10, **kwargs)
    _log_response(method, url, response)
    return response


def _log_response(method: str, url: str, response: requests.Response) -> None:
    if response.ok:
        print(f"[discord] {method} {url} -> {response.status_code}")
    else:
        print(f"[discord] {method} {url} -> {response.status_code} body={response.text}")


def _extract_role_id(role_id: str) -> str:
    """Strip Discord mention format (<@&id>) if present, returning just the numeric snowflake."""
    if role_id and role_id.startswith("<@&") and role_id.endswith(">"):
        return role_id[3:-1]
    return role_id


def add_discord_role(guild_id: str, user_id: str, role_id: str) -> bool:
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{_extract_role_id(role_id)}"
    response = discord_request("PUT", url)
    return response.status_code == 204


def search_discord_member(guild_id: str, username: str) -> str | None:
    """Look up a Discord snowflake by exact username handle via guild member search."""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/search"
    response = discord_request("GET", url, params={"query": username, "limit": 10})
    if response.status_code != 200:
        return None
    for member in response.json():
        if member.get("user", {}).get("username") == username:
            return member["user"]["id"]
    return None


def send_channel_message(channel_id: str, content: str) -> None:
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    discord_request("POST", url, json={"content": content})


def enqueue_remove_roles(server_id: str, user_ids: list, role_id: str, sqs_queue) -> None:
    clean_role_id = _extract_role_id(role_id)
    batch = []
    for idx, uid in enumerate(user_ids):
        batch.append({
            "Id": str(idx),
            "MessageBody": json.dumps({"guild_id": server_id, "user_id": uid, "role_id": clean_role_id}),
        })
        if len(batch) == 10:
            sqs_queue.send_messages(Entries=batch)
            batch = []
    if batch:
        sqs_queue.send_messages(Entries=batch)
