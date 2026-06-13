import logging

import requests

import discord_api

logger = logging.getLogger()


def send_followup(application_id: str, interaction_token: str, content: str, *, allowed_mentions: dict = None, flags: int = 0) -> None:
    """POST a followup message to the Discord interaction webhook."""
    url = f"{discord_api.DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}"
    payload = {"content": content}
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions
    if flags:
        payload["flags"] = flags
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        logger.info(f"[sheets_agent] followup sent OK status={resp.status_code}")
    else:
        logger.error(f"[sheets_agent] followup failed status={resp.status_code} body={resp.text}")
