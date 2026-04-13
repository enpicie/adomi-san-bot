import requests

from discord_api import DISCORD_API_BASE


def send_followup(application_id: str, interaction_token: str, content: str, *, allowed_mentions: dict = None, flags: int = 0) -> None:
    """POST a followup message to the Discord interaction webhook."""
    url = f"{DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}"
    payload = {"content": content}
    if allowed_mentions is not None:
        payload["allowed_mentions"] = allowed_mentions
    if flags:
        payload["flags"] = flags
    resp = requests.post(url, json=payload)
    if resp.ok:
        print(f"[sheets_agent] followup sent OK status={resp.status_code}")
    else:
        print(f"[sheets_agent] followup failed status={resp.status_code} body={resp.text}")
