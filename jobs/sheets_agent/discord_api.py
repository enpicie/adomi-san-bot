import json
import time

import requests

from enum import Enum

import constants


class RoleAssignmentResult(Enum):
    OK = "ok"
    FORBIDDEN = "forbidden"
    ERROR = "error"


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


def add_discord_role(guild_id: str, user_id: str, role_id: str) -> RoleAssignmentResult:
    """Returns RoleAssignmentResult.OK on success, .FORBIDDEN on 403, .ERROR otherwise."""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{_extract_role_id(role_id)}"
    response = discord_request("PUT", url)
    if response.status_code == 204:
        return RoleAssignmentResult.OK
    if response.status_code == 403:
        return RoleAssignmentResult.FORBIDDEN
    return RoleAssignmentResult.ERROR


def search_discord_member(guild_id: str, username: str, participant_name: str | None = None) -> str | None:
    """Look up a Discord snowflake by username handle, with case-insensitive fallback matching
    against username, nick, and global_name. If not found and participant_name is provided (and
    differs from the handle), retries the search using participant_name as the query."""
    queries = [username]
    if participant_name and participant_name.strip().lower() != username.strip().lower():
        queries.append(participant_name)

    for query in queries:
        url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/search"
        response = discord_request("GET", url, params={"query": query, "limit": 10})
        if response.status_code != 200:
            continue
        query_lower = query.strip().lower()
        for member in response.json():
            user = member.get("user", {})
            if any(
                (user.get(field) or "").strip().lower() == query_lower
                for field in ("username", "global_name")
            ) or (member.get("nick") or "").strip().lower() == query_lower:
                return user["id"]
    return None


def search_member_by_display_name(guild_id: str, display_name: str) -> tuple[str, str] | None:
    """Look up a guild member by server nick or global display name.
    Returns (snowflake, username_handle) if exactly one member matches exactly, otherwise None."""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/search"
    response = discord_request("GET", url, params={"query": display_name, "limit": 10})
    if response.status_code != 200:
        return None
    matches = []
    display_name_lower = display_name.lower()
    for member in response.json():
        nick = member.get("nick") or ""
        global_name = member.get("user", {}).get("global_name") or ""
        if nick.lower() == display_name_lower or global_name.lower() == display_name_lower:
            matches.append((member["user"]["id"], member["user"]["username"]))
    return matches[0] if len(matches) == 1 else None


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
