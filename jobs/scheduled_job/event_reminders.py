import logging
from datetime import datetime, timedelta, timezone as dt_timezone

import db
import discord_api

logger = logging.getLogger()

_REMINDER_WINDOW_HOURS = 24


def check_and_send_reminder(table, server_id, event_id, server_config):
    """Check if an active event is due for a reminder and send it if so.

    Loads and returns the server_config (passing it back so the caller can cache it).
    A reminder is sent when all of the following are true:
      - should_post_reminder is True on the event
      - did_post_reminder is False on the event
      - the event start_time is within the next 24 hours
      - announcement_channel_id is configured on the server
    """
    event_record = db.get_event_record(table, server_id, event_id)
    if not event_record:
        logger.warning(f"Event record not found for {event_id} in server {server_id} during reminder check")
        return server_config

    if not event_record.get("should_post_reminder"):
        return server_config

    if event_record.get("did_post_reminder"):
        return server_config

    start_time_str = event_record.get("start_time")
    if not start_time_str:
        return server_config

    try:
        start_dt = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    except ValueError:
        logger.error(f"Could not parse start_time '{start_time_str}' for event {event_id}")
        return server_config

    now = datetime.now(dt_timezone.utc)
    if not (now < start_dt <= now + timedelta(hours=_REMINDER_WINDOW_HOURS)):
        return server_config

    if server_config is None:
        server_config = db.get_server_config(table, server_id)

    announcement_channel_id = event_record.get("reminder_channel_id") or (server_config.get("announcement_channel_id") if server_config else None)
    if not announcement_channel_id:
        logger.info(f"No announcement_channel_id configured for server {server_id}, skipping reminder for event {event_id}")
        return server_config

    start_epoch = int(start_dt.timestamp())
    event_name = event_record.get("event_name") or event_id

    message = f"## 📣 {event_name} is coming up <t:{start_epoch}:R>\n Starting <t:{start_epoch}:F>!"

    announcement_role_id = event_record.get("reminder_role_id") or (server_config.get("announcement_role_id") if server_config else None)
    if announcement_role_id:
        message = f"<@&{announcement_role_id}> {message}"

    sent = discord_api.send_channel_message(announcement_channel_id, message)
    if sent:
        db.mark_event_reminder_sent(table, server_id, event_id)
        logger.info(f"Sent reminder for event {event_id} in server {server_id}")
    else:
        logger.error(f"Failed to send reminder for event {event_id} in server {server_id}")

    return server_config
