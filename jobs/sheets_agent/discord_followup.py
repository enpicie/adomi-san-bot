import requests

from discord_api import DISCORD_API_BASE


def send_followup(application_id: str, interaction_token: str, content: str) -> None:
    """POST a followup message to the Discord interaction webhook."""
    url = f"{DISCORD_API_BASE}/webhooks/{application_id}/{interaction_token}"
    resp = requests.post(url, json={"content": content})
    if resp.ok:
        print(f"[sheets_agent] followup sent OK status={resp.status_code}")
    else:
        print(f"[sheets_agent] followup failed status={resp.status_code} body={resp.text}")
