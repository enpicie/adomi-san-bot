import os

import requests

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
_DISCORD_API = "https://discord.com/api/v10"


def send_oauth_notification(server_config: dict, discord_user_id: str):
    """Send a notification to the server's notification channel if configured."""
    notification_channel_id = server_config.get("notification_channel_id")
    if not notification_channel_id:
        return

    message = (
        f"✅ <@{discord_user_id}> has linked their start.gg organizer account to this server. "
        "Score reporting via `/startgg-report-score` is now enabled."
    )
    if server_config.get("ping_organizers"):
        organizer_role = server_config.get("organizer_role")
        if organizer_role:
            message = f"<@&{organizer_role}> {message}"

    requests.post(
        f"{_DISCORD_API}/channels/{notification_channel_id}/messages",
        headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"},
        json={"content": message},
        timeout=5,
    )
