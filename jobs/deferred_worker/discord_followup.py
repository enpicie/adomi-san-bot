import logging

import requests

import worker_discord_api as discord_api

logger = logging.getLogger()

DISCORD_MESSAGE_LIMIT = 2000
_TRUNCATION_MARKER = "\n…(message trimmed to fit Discord's limit)"


def _fit_to_discord_limit(content: str) -> str:
    """Trim content that Discord would reject outright, so the user still gets a reply."""
    if len(content) <= DISCORD_MESSAGE_LIMIT:
        return content
    logger.warning(f"[followup] trimming followup from {len(content)} to {DISCORD_MESSAGE_LIMIT} characters")
    return content[:DISCORD_MESSAGE_LIMIT - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER


def send_followup(application_id: str, interaction_token: str, content: str, *, allowed_mentions: dict = None, flags: int = 0) -> None:
    """POST a followup message to the Discord interaction webhook."""
    url = f"{discord_api.DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}"
    payload = {"content": _fit_to_discord_limit(content)}
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions
    if flags:
        payload["flags"] = flags
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        logger.info(f"[followup] followup sent OK status={resp.status_code}")
    else:
        logger.error(f"[followup] followup failed status={resp.status_code} body={resp.text}")
